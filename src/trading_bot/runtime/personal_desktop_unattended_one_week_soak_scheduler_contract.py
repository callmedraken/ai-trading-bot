"""Pure Architecture-122 D10 task target and bounded deployment specification."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime
from pathlib import PureWindowsPath
from zoneinfo import ZoneInfo

from trading_bot.runtime import (
    personal_desktop_unattended_capture_warmup_scheduler_contract as capture_contract,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_window import (
    OneWeekSoakWindow,
    build_one_week_soak_window,
)
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    PersonalDesktopUnattendedSchedulerContract,
    PersonalDesktopUnattendedSchedulerDeploymentSpec,
    build_personal_desktop_unattended_scheduler_deployment_spec,
)

D10_SCHEDULER_CONTRACT_SCHEMA = "personal-desktop-one-week-soak-scheduler-contract/v2"
D10_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA = (
    "personal-desktop-one-week-soak-scheduler-deployment-spec/v2"
)
D10_ROOT = PureWindowsPath(r"F:\AITradingBot\D10")
D10_LAUNCH_GUARD = D10_ROOT / "launch-guard.py"
D10_SOURCE_ROOT = D10_ROOT / "source"
D10_SECOND_STAGE_LAUNCHER = (
    D10_SOURCE_ROOT / "scripts" / "run_personal_desktop_unattended_one_week_soak.py"
)
D10_CACHE_PREFIX = D10_ROOT / "no-pycache"
D10_GUARD_SOURCE_RELATIVE_PATH = "scripts/run_personal_desktop_d10_launch_guard.py"
D10_LAUNCHER_SOURCE_RELATIVE_PATH = (
    "scripts/run_personal_desktop_unattended_one_week_soak.py"
)
D10_INTERPRETER_ARGUMENTS = (
    "-I",
    "-S",
    "-B",
    "-X",
    f"pycache_prefix={D10_CACHE_PREFIX}",
)
D10_GUARD_ARGUMENTS = (*D10_INTERPRETER_ARGUMENTS, str(D10_LAUNCH_GUARD))
D10_SECOND_STAGE_ARGUMENTS = (
    *D10_INTERPRETER_ARGUMENTS,
    str(D10_SECOND_STAGE_LAUNCHER),
)

_D5 = capture_contract.personal_desktop_unattended_capture_warmup_scheduler_contract()
D10_SCHEDULER_CONTRACT = replace(
    _D5,
    schema=D10_SCHEDULER_CONTRACT_SCHEMA,
    interpreter_arguments=D10_INTERPRETER_ARGUMENTS,
    launcher=D10_LAUNCH_GUARD,
    working_directory=D10_ROOT,
)
_REVIEWED_DIFFERENCES = frozenset(
    {"schema", "interpreter_arguments", "launcher", "working_directory"}
)


@dataclass(frozen=True, slots=True)
class OneWeekSoakSchedulerDeploymentSpec:
    """One task definition plus its exact bounded trigger interval."""

    schema: str
    task: PersonalDesktopUnattendedSchedulerDeploymentSpec
    window: OneWeekSoakWindow
    end_boundary: datetime

    def __post_init__(self) -> None:
        expected_task = (
            replace(
                build_personal_desktop_unattended_scheduler_deployment_spec(
                    self.window.activation_utc
                ),
                arguments=D10_GUARD_ARGUMENTS,
                working_directory=D10_ROOT,
            )
            if type(self.window) is OneWeekSoakWindow
            else None
        )
        if (
            self.schema != D10_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA
            or type(self.task) is not PersonalDesktopUnattendedSchedulerDeploymentSpec
            or type(self.window) is not OneWeekSoakWindow
            or self.task != expected_task
            or type(self.end_boundary) is not datetime
            or self.end_boundary.tzinfo != ZoneInfo(_D5.source_timezone)
            or self.end_boundary
            != self.window.end_utc.astimezone(ZoneInfo(_D5.source_timezone))
            or self.task.start_boundary.astimezone(self.window.activation_utc.tzinfo)
            >= self.window.end_utc
            or self.task.semantic_arguments
            or self.task.arguments != D10_GUARD_ARGUMENTS
            or self.task.restart_on_failure
            or self.task.restart_count != 0
        ):
            raise ValueError("D10 bounded scheduler specification is invalid")


def one_week_soak_scheduler_contract() -> PersonalDesktopUnattendedSchedulerContract:
    return D10_SCHEDULER_CONTRACT


def is_frozen_one_week_soak_scheduler_contract(contract: object) -> bool:
    if type(contract) is not PersonalDesktopUnattendedSchedulerContract:
        return False
    changed = {
        field.name
        for field in fields(PersonalDesktopUnattendedSchedulerContract)
        if getattr(contract, field.name) != getattr(_D5, field.name)
    }
    return contract == D10_SCHEDULER_CONTRACT and changed == _REVIEWED_DIFFERENCES


def build_one_week_soak_scheduler_deployment_spec(
    activation: datetime,
) -> OneWeekSoakSchedulerDeploymentSpec:
    """Build the later operator's source specification without scheduler I/O."""

    if not is_frozen_one_week_soak_scheduler_contract(D10_SCHEDULER_CONTRACT):
        raise RuntimeError("D10 scheduler contract differs from the reviewed target")
    window = build_one_week_soak_window(activation)
    base = build_personal_desktop_unattended_scheduler_deployment_spec(
        window.activation_utc
    )
    task = replace(base, arguments=D10_GUARD_ARGUMENTS, working_directory=D10_ROOT)
    return OneWeekSoakSchedulerDeploymentSpec(
        D10_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA,
        task,
        window,
        window.end_utc.astimezone(ZoneInfo(D10_SCHEDULER_CONTRACT.source_timezone)),
    )
