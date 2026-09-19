"""Pure PD4-D2 Windows Task Scheduler deployment contract.

Task Scheduler is an untrusted zero-argument wake-up source. This module
freezes the reviewed task definition and can derive a registration
specification, but it never inspects or mutates Task Scheduler state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import PureWindowsPath
from zoneinfo import ZoneInfo

PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA = (
    "personal-desktop-unattended-scheduler-contract/v2"
)
PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA = (
    "personal-desktop-unattended-scheduler-deployment-spec/v1"
)

_PACIFIC_SOURCE_TIMEZONE = "America/Los_Angeles"
_PACIFIC = ZoneInfo(_PACIFIC_SOURCE_TIMEZONE)


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedSchedulerContract:
    """Immutable source-owned task definition; never trading authority."""

    schema: str
    task_path: str
    production_interpreter: PureWindowsPath
    interpreter_arguments: tuple[str, ...]
    launcher: PureWindowsPath
    semantic_arguments: tuple[str, ...]
    working_directory: PureWindowsPath
    scheduler_owned_environment: tuple[str, ...]
    principal: str
    principal_sid: str
    logon_type: str
    run_level: str
    task_scheduler_run_level: str
    trigger_type: str
    host_timezone: str
    source_timezone: str
    local_wall_clock_time: time
    days_interval: int
    start_when_available: bool
    random_delay: timedelta | None
    repetition: timedelta | None
    enabled: bool
    allow_start_on_demand: bool
    wake_to_run: bool
    run_only_if_idle: bool
    run_only_if_network_available: bool
    disallow_start_if_on_batteries: bool
    stop_if_going_on_batteries: bool
    hidden: bool
    multiple_instances_policy: str
    restart_on_failure: bool
    restart_count: int
    execution_time_limit: str
    priority: int
    working_directory_is_authoritative: bool
    trigger_is_authoritative: bool
    trigger_occurrence_is_authoritative: bool
    trigger_count_is_authoritative: bool
    next_run_time_is_authoritative: bool
    task_history_is_authoritative: bool
    previous_exit_is_authoritative: bool
    process_lifetime_is_authoritative: bool
    task_state_is_authoritative: bool
    overlap_policy_is_authoritative: bool
    authoritative_overlap_control: str
    timing_policy_is_frozen: bool
    installation_is_authorized: bool
    modification_is_authorized: bool
    installation_requires_separate_operator_effect_checkpoint: bool
    absent_task_disposition: str
    exact_existing_task_disposition: str
    conflicting_existing_task_disposition: str


PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT = (
    PersonalDesktopUnattendedSchedulerContract(
        schema=PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA,
        task_path=r"\AITradingBot-PD4-UnattendedPaper-v1",
        production_interpreter=PureWindowsPath(r"F:\AITradingBot\runtime\python.exe"),
        interpreter_arguments=("-I",),
        launcher=PureWindowsPath(
            r"F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
            r"\run_personal_desktop_unattended_paper_operation.py"
        ),
        semantic_arguments=(),
        working_directory=PureWindowsPath(
            r"F:\AI\worktrees\ai-trading-bot-personal-desktop"
        ),
        scheduler_owned_environment=(),
        principal=r"DESKTOP-I4DOKM7\Trading",
        principal_sid="S-1-5-21-1397534616-3988210162-180023805-1009",
        logon_type="Password",
        run_level="LeastPrivilege",
        task_scheduler_run_level="LUA",
        trigger_type="DAILY",
        host_timezone="Pacific Standard Time",
        source_timezone=_PACIFIC_SOURCE_TIMEZONE,
        local_wall_clock_time=time(1, 30),
        days_interval=1,
        start_when_available=True,
        random_delay=None,
        repetition=None,
        enabled=True,
        allow_start_on_demand=True,
        wake_to_run=True,
        run_only_if_idle=False,
        run_only_if_network_available=False,
        disallow_start_if_on_batteries=False,
        stop_if_going_on_batteries=False,
        hidden=False,
        multiple_instances_policy="IgnoreNew",
        restart_on_failure=False,
        restart_count=0,
        execution_time_limit="PT1H",
        priority=7,
        working_directory_is_authoritative=False,
        trigger_is_authoritative=False,
        trigger_occurrence_is_authoritative=False,
        trigger_count_is_authoritative=False,
        next_run_time_is_authoritative=False,
        task_history_is_authoritative=False,
        previous_exit_is_authoritative=False,
        process_lifetime_is_authoritative=False,
        task_state_is_authoritative=False,
        overlap_policy_is_authoritative=False,
        authoritative_overlap_control="PD2A_ACCOUNT_MUTEX",
        timing_policy_is_frozen=True,
        installation_is_authorized=True,
        modification_is_authorized=False,
        installation_requires_separate_operator_effect_checkpoint=True,
        absent_task_disposition="CREATE_AT_OPERATOR_EFFECT_CHECKPOINT",
        exact_existing_task_disposition="ACCEPT_READ_ONLY",
        conflicting_existing_task_disposition="BLOCKED",
    )
)


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedSchedulerDeploymentSpec:
    """Exact non-mutating operator input for later task registration."""

    schema: str
    task_path: str
    principal: str
    principal_sid: str
    logon_type: str
    run_level: str
    task_scheduler_run_level: str
    executable: PureWindowsPath
    arguments: tuple[str, ...]
    working_directory: PureWindowsPath
    trigger_type: str
    host_timezone: str
    start_boundary: datetime
    days_interval: int
    start_when_available: bool
    random_delay: timedelta | None
    repetition: timedelta | None
    enabled: bool
    allow_start_on_demand: bool
    wake_to_run: bool
    run_only_if_idle: bool
    run_only_if_network_available: bool
    disallow_start_if_on_batteries: bool
    stop_if_going_on_batteries: bool
    hidden: bool
    multiple_instances_policy: str
    restart_on_failure: bool
    restart_count: int
    execution_time_limit: str
    priority: int
    semantic_arguments: tuple[str, ...]
    scheduler_owned_environment: tuple[str, ...]


def is_frozen_personal_desktop_unattended_scheduler_contract(
    contract: object,
) -> bool:
    """Return whether *contract* is the exact reviewed source-owned value."""

    return (
        type(contract) is PersonalDesktopUnattendedSchedulerContract
        and contract == PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    )


def personal_desktop_unattended_scheduler_contract() -> (
    PersonalDesktopUnattendedSchedulerContract
):
    """Return the fixed source contract without consulting scheduler state."""

    return PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT


def build_personal_desktop_unattended_scheduler_deployment_spec(
    installation_observed_at: datetime,
) -> PersonalDesktopUnattendedSchedulerDeploymentSpec:
    """Derive the first future 01:30 Pacific registration boundary purely."""

    if (
        type(installation_observed_at) is not datetime
        or installation_observed_at.tzinfo is None
        or installation_observed_at.utcoffset() is None
    ):
        raise ValueError("installation observation must be an aware datetime")
    contract = personal_desktop_unattended_scheduler_contract()
    if not is_frozen_personal_desktop_unattended_scheduler_contract(contract):
        raise RuntimeError("scheduler contract is not the frozen source value")
    start_boundary = _next_future_pacific_wall_clock(
        installation_observed_at, contract.local_wall_clock_time
    )
    return PersonalDesktopUnattendedSchedulerDeploymentSpec(
        schema=PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA,
        task_path=contract.task_path,
        principal=contract.principal,
        principal_sid=contract.principal_sid,
        logon_type=contract.logon_type,
        run_level=contract.run_level,
        task_scheduler_run_level=contract.task_scheduler_run_level,
        executable=contract.production_interpreter,
        arguments=(*contract.interpreter_arguments, str(contract.launcher)),
        working_directory=contract.working_directory,
        trigger_type=contract.trigger_type,
        host_timezone=contract.host_timezone,
        start_boundary=start_boundary,
        days_interval=contract.days_interval,
        start_when_available=contract.start_when_available,
        random_delay=contract.random_delay,
        repetition=contract.repetition,
        enabled=contract.enabled,
        allow_start_on_demand=contract.allow_start_on_demand,
        wake_to_run=contract.wake_to_run,
        run_only_if_idle=contract.run_only_if_idle,
        run_only_if_network_available=contract.run_only_if_network_available,
        disallow_start_if_on_batteries=contract.disallow_start_if_on_batteries,
        stop_if_going_on_batteries=contract.stop_if_going_on_batteries,
        hidden=contract.hidden,
        multiple_instances_policy=contract.multiple_instances_policy,
        restart_on_failure=contract.restart_on_failure,
        restart_count=contract.restart_count,
        execution_time_limit=contract.execution_time_limit,
        priority=contract.priority,
        semantic_arguments=contract.semantic_arguments,
        scheduler_owned_environment=contract.scheduler_owned_environment,
    )


def _next_future_pacific_wall_clock(
    observed_at: datetime, wall_clock: time
) -> datetime:
    observed_utc = observed_at.astimezone(UTC)
    first_date = observed_utc.astimezone(_PACIFIC).date()
    for day_offset in range(3):
        local_date = first_date + timedelta(days=day_offset)
        candidates = _pacific_wall_clock_candidates(local_date, wall_clock)
        future = [value for value in candidates if value.astimezone(UTC) > observed_utc]
        if future:
            return min(future, key=lambda value: value.astimezone(UTC))
    raise RuntimeError("could not derive a future scheduler start boundary")


def _pacific_wall_clock_candidates(
    local_date: date, wall_clock: time
) -> tuple[datetime, ...]:
    naive = datetime.combine(local_date, wall_clock)
    candidates: dict[datetime, datetime] = {}
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=_PACIFIC, fold=fold)
        round_trip = candidate.astimezone(UTC).astimezone(_PACIFIC)
        if round_trip.replace(tzinfo=None) == naive:
            candidates[candidate.astimezone(UTC)] = candidate
    return tuple(candidates[key] for key in sorted(candidates))
