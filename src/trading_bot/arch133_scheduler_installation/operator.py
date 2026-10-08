"""Q133-3 orchestration, closed evidence and a single fixed native transport."""

from __future__ import annotations

import ctypes
import getpass
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from trading_bot.arch133_scheduler_installation import admission
from trading_bot.arch133_scheduler_installation.specification import (
    build_unattended_scheduler_spec,
)
from trading_bot.arch133_verifier.activation import ReviewPaperActivation
from trading_bot.arch133_verifier.scheduler import UnattendedSchedulerSpec

PLAN_SCHEMA = "arch133p-scheduler-installation-plan/v1"
RESULT_SCHEMA = "arch133p-scheduler-installation/v1"
OBSERVE_SCHEMA = "arch133p-scheduler-observation/v1"
INSTALL_SCHEMA = "arch133p-scheduler-registration/v1"
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
ZERO_EFFECTS = {
    name: 0
    for name in (
        "credential_reads",
        "credential_writes",
        "provider_calls",
        "scheduler_reads",
        "scheduler_writes",
        "paper_mutations",
        "state_mutations",
        "acl_mutations",
        "wake_delegations",
        "execution_delegations",
        "consumed_wake_authority",
        "broker_effects",
        "manual_task_starts",
    )
}
# Disabled until separately reviewed Q133-4 enabling authority exists.
WINDOWS_SETTINGS = {
    "logon_type": "Password",
    "enabled": False,
    "allow_demand_start": False,
    "disallow_start_if_on_batteries": True,
    "stop_if_going_on_batteries": True,
    "run_only_if_network_available": False,
    "run_only_if_idle": False,
    "wake_to_run": False,
    "hidden": False,
    "execution_time_limit": "PT1H",
    "priority": 7,
    "compatibility": 2,
    "allow_hard_terminate": True,
    "delete_expired_task_after": "",
    "idle_stop_on_idle_end": True,
    "idle_restart_on_idle": False,
    "network_id": "",
    "network_name": "",
}
TASK_XML = (
    r"""<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo>
<URI>\AITradingBot-Arch133-SingleSessionReviewPaper-v1</URI>
</RegistrationInfo>
<Triggers>
<TimeTrigger>
<StartBoundary>{start}</StartBoundary>
<EndBoundary>{end}</EndBoundary>
<Enabled>true</Enabled>
</TimeTrigger>
</Triggers>
<Principals>
<Principal id="Trading">
<UserId>S-1-5-21-1397534616-3988210162-180023805-1009</UserId>
<LogonType>Password</LogonType>
<RunLevel>LeastPrivilege</RunLevel>
</Principal>
</Principals>
<Settings>
<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
<AllowHardTerminate>true</AllowHardTerminate>
<StartWhenAvailable>false</StartWhenAvailable>
<RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
<IdleSettings>
<StopOnIdleEnd>true</StopOnIdleEnd>
<RestartOnIdle>false</RestartOnIdle>
</IdleSettings>
<AllowStartOnDemand>false</AllowStartOnDemand>
<Enabled>false</Enabled>
<Hidden>false</Hidden>
<RunOnlyIfIdle>false</RunOnlyIfIdle>
<WakeToRun>false</WakeToRun>
<ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
<Priority>7</Priority>
</Settings>
<Actions Context="Trading">
<Exec>
<Command>F:\AITradingBot\runtime\python.exe</Command>
"""
    + r"<Arguments>-I -B "
    + r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g\scripts"
    + r"\run_arch133_unattended_review_paper.py</Arguments>"
    + r"""
<WorkingDirectory>F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g</WorkingDirectory>
</Exec>
</Actions>
</Task>"""
)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def boundary(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def xml_fingerprint(xml: str) -> str:
    """Closed semantic tree including every element/attribute, never artifact bytes."""

    def frame(value: str) -> str:
        return f"{len(value)}:{value}"

    def visit(node: ET.Element) -> str:
        attributes = "".join(
            frame(k) + frame(v) for k, v in sorted(node.attrib.items())
        )
        if any((child.tail or "").strip() for child in node):
            raise ValueError
        return (
            "("
            + frame(node.tag)
            + frame(attributes)
            + frame((node.text or "").strip())
            + "".join(visit(child) for child in node)
            + ")"
        )

    return hashlib.sha256(visit(ET.fromstring(xml)).encode("utf-8")).hexdigest()


def desired_task(spec: UnattendedSchedulerSpec) -> dict:
    return {
        "task_path": spec.task_path,
        "principal": spec.principal,
        "principal_sid": spec.principal_sid,
        "run_level": spec.run_level,
        "executable": spec.executable,
        "arguments": list(spec.arguments),
        "working_directory": spec.working_directory,
        "start_boundary": boundary(spec.start_boundary),
        "end_boundary": boundary(spec.end_boundary),
        "trigger_type": spec.trigger_type,
        "multiple_instances_policy": spec.multiple_instances_policy,
        "restart_count": spec.restart_count,
        "restart_interval": spec.restart_interval,
        "repetition": spec.repetition,
        "start_when_available": spec.start_when_available,
        "semantic_arguments": [],
        "scheduler_owned_environment": [],
        "scheduler_is_authority": False,
        "windows_settings": WINDOWS_SETTINGS,
        "projection_sha256": xml_fingerprint(
            TASK_XML.format(
                start=boundary(spec.start_boundary), end=boundary(spec.end_boundary)
            )
        ),
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_window(spec: UnattendedSchedulerSpec) -> None:
    now = _utc_now()
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError
    if not now < spec.start_boundary < spec.end_boundary:
        raise StaleWindow


class StaleWindow(ValueError):
    """No time trigger may be installed at or after its start."""


def _native(script: str, request: dict | None = None) -> dict:
    # Caller never chooses a native path, code, environment payload or argument.
    if script not in ("arch133_scheduler_observe.ps1", "arch133_scheduler_install.ps1"):
        raise ValueError
    payload = None
    try:
        payload = "" if request is None else canonical(request) + "\n"
        result = subprocess.run(
            [
                POWERSHELL,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(admission.SOURCE_ROOT / "scripts" / script),
            ],
            input=payload,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=False,
            cwd=admission.SOURCE_ROOT,
            env={"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
        )
        if result.stderr or len(result.stdout) > 16384:
            raise ValueError
        data = json.loads(result.stdout)
        if type(data) is not dict:
            raise ValueError
        if script == "arch133_scheduler_observe.ps1":
            if result.returncode != 0:
                raise ValueError
        else:
            expected = {
                0: ("CALL_RETURNED", 1),
                1: ("NOT_CALLED", 0),
                2: ("INDETERMINATE", 1),
            }.get(result.returncode)
            if (
                expected is None
                or type(data.get("registration_attempts")) is not int
                or data
                != {
                    "schema": INSTALL_SCHEMA,
                    "disposition": expected[0],
                    "registration_attempts": expected[1],
                }
            ):
                raise ValueError
        return data
    finally:
        payload = None
        if request is not None:
            request["password"] = None


def _observe(counters: dict) -> dict:
    counters["scheduler_reads"] += 2
    data = _native("arch133_scheduler_observe.ps1")
    if set(data) != {"schema", "first", "second"} or data["schema"] != OBSERVE_SCHEMA:
        raise ValueError
    if data["first"] != data["second"]:
        raise ValueError
    observation = data["first"]
    if type(observation) is not dict:
        raise ValueError
    if observation == {"status": "ABSENT"}:
        return observation
    if (
        set(observation) != {"status", "projection_sha256", "xml_sha256"}
        or observation["status"] != "PRESENT"
    ):
        raise ValueError
    if any(
        type(observation[k]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", observation[k]) is None
        for k in ("projection_sha256", "xml_sha256")
    ):
        raise ValueError
    return observation


def _construct_plan(
    counters: dict,
) -> tuple[dict, ReviewPaperActivation, UnattendedSchedulerSpec]:
    activation, facts = admission.observe_admission()
    spec = build_unattended_scheduler_spec(activation)
    _require_window(spec)
    desired = desired_task(spec)
    observed = _observe(counters)
    # Scheduler observation is not allowed to hide admission drift or elapsed time.
    repeated_activation, repeated_facts = admission.observe_admission()
    if repeated_activation != activation or repeated_facts != facts:
        raise ValueError
    _require_window(spec)
    disposition = (
        "ABSENT"
        if observed["status"] == "ABSENT"
        else (
            "ALREADY_MATCHING"
            if observed["projection_sha256"] == desired["projection_sha256"]
            else "UNEXPECTED_EXISTING"
        )
    )
    material = {
        "schema": PLAN_SCHEMA,
        "disposition": disposition,
        "admission_sha256": sha256(facts),
        "activation_sha256": hashlib.sha256(activation.to_json().encode()).hexdigest(),
        "desired_task": desired,
        "observed": observed,
    }
    return {**material, "plan_sha256": sha256(material)}, activation, spec


def _require_interactive_console() -> None:
    # Match the reviewed native-console proof; isatty alone accepts redirected devices.
    if (
        sys.platform != "win32"
        or sys.stdin is not sys.__stdin__
        or sys.stdout is not sys.__stdout__
        or not sys.stdin.isatty()
        or not sys.stdout.isatty()
    ):
        raise ValueError
    from ctypes import wintypes

    kernel = ctypes.WinDLL(r"C:\Windows\System32\kernel32.dll", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetConsoleMode.restype = wintypes.BOOL
    for number in (-10, -11):
        mode = wintypes.DWORD()
        if not kernel.GetConsoleMode(
            kernel.GetStdHandle(number & 0xFFFFFFFF), ctypes.byref(mode)
        ):
            raise ValueError


def _read_password() -> str:
    _require_interactive_console()
    secret = getpass.getpass("Trading password for protected Q133-3: ")
    if type(secret) is not str or not secret or len(secret) > 1024 or "\x00" in secret:
        raise ValueError
    return secret


def _register(
    activation: ReviewPaperActivation, spec: UnattendedSchedulerSpec, password: str
) -> dict:
    return _native(
        "arch133_scheduler_install.ps1",
        {
            "activation_sha256": hashlib.sha256(
                activation.to_json().encode()
            ).hexdigest(),
            "start_boundary": boundary(spec.start_boundary),
            "end_boundary": boundary(spec.end_boundary),
            "password": password,
        },
    )


def operate(mode: str, reviewed_plan_sha256: str | None = None) -> dict:
    """Closed modes; dependency seams are private and fake-only in source tests."""
    counters = dict(ZERO_EFFECTS)
    attempted = False
    password = None
    disposition = "ADMISSION_BLOCKED"
    result = {"schema": RESULT_SCHEMA, "status": "BLOCKED"}
    try:
        if (
            mode not in ("plan", "execute-once")
            or (mode == "plan" and reviewed_plan_sha256 is not None)
            or (
                mode == "execute-once"
                and (
                    type(reviewed_plan_sha256) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", reviewed_plan_sha256) is None
                )
            )
        ):
            raise ValueError
        plan, activation, spec = _construct_plan(counters)
        disposition = plan["disposition"]
        if mode == "plan":
            result = {
                **plan,
                "status": "BLOCKED" if disposition == "UNEXPECTED_EXISTING" else "PASS",
            }
        else:
            if plan["plan_sha256"] != reviewed_plan_sha256:
                disposition = "PLAN_DRIFT"
                raise ValueError
            if disposition == "UNEXPECTED_EXISTING":
                raise ValueError
            repeated, _, _ = _construct_plan(counters)
            if repeated != plan:
                disposition = "PLAN_DRIFT"
                raise ValueError
            if disposition == "ABSENT":
                password = _read_password()
                counters["credential_reads"] = 1
            with admission.registration_guard():
                repeated, _, _ = _construct_plan(counters)
                if repeated != plan:
                    disposition = (
                        "PASSWORD_PAUSE_DRIFT" if password is not None else "PLAN_DRIFT"
                    )
                    raise ValueError
                if disposition == "ABSENT":
                    _require_window(spec)
                    attempted = True
                    counters["scheduler_writes"] = 1
                    counters["scheduler_reads"] += 2
                    native = _register(activation, spec, password)
                    password = None
                    if native == {
                        "schema": INSTALL_SCHEMA,
                        "disposition": "NOT_CALLED",
                        "registration_attempts": 0,
                    }:
                        attempted = False
                        counters["scheduler_writes"] = 0
                        disposition = "NATIVE_BLOCKED"
                        raise ValueError
                    if native != {
                        "schema": INSTALL_SCHEMA,
                        "disposition": "CALL_RETURNED",
                        "registration_attempts": 1,
                    }:
                        raise ValueError
                final = _observe(counters)
                if (
                    final.get("projection_sha256")
                    != plan["desired_task"]["projection_sha256"]
                ):
                    raise ValueError
                final_activation, final_facts = admission.observe_admission()
                if (
                    final_activation != activation
                    or sha256(final_facts) != plan["admission_sha256"]
                ):
                    raise ValueError
            result = {
                "schema": RESULT_SCHEMA,
                "status": "PASS",
                "plan_sha256": plan["plan_sha256"],
            }
            disposition = "CREATED_VERIFIED" if attempted else "ALREADY_MATCHING"
    except StaleWindow:
        disposition = "INDETERMINATE" if attempted else "STALE_EXPIRED"
        result = {
            "schema": RESULT_SCHEMA,
            "status": "INDETERMINATE" if attempted else "BLOCKED",
        }
    except BaseException:
        result = {
            "schema": RESULT_SCHEMA,
            "status": "INDETERMINATE" if attempted else "BLOCKED",
        }
        if attempted:
            disposition = "INDETERMINATE"
    finally:
        password = None
    return {**result, "disposition": disposition, **counters}


def parse_arguments(args: list[str]) -> tuple[str, str | None]:
    if args == ["plan"]:
        return "plan", None
    if (
        len(args) == 3
        and args[:2] == ["execute-once", "--reviewed-plan-sha256"]
        and re.fullmatch(r"[0-9a-f]{64}", args[2])
    ):
        return "execute-once", args[2]
    raise ValueError


def main(argv: list[str] | None = None) -> int:
    try:
        mode, reviewed = parse_arguments(sys.argv[1:] if argv is None else argv)
        result = operate(mode, reviewed)
    except BaseException:
        result = {
            "schema": RESULT_SCHEMA,
            "status": "BLOCKED",
            "disposition": "ARGUMENTS_BLOCKED",
            **ZERO_EFFECTS,
        }
    print(canonical(result))
    return 0 if result["status"] == "PASS" else 3
