"""Pure PD4-E Windows Task Scheduler launch contract.

The scheduler is an untrusted wake-up source.  This module describes the one
reviewed task action without installing a task or granting trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath

PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA = (
    "personal-desktop-unattended-scheduler-contract/v1"
)


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedSchedulerContract:
    """Immutable diagnostics-only scheduler contract; never an authority."""

    schema: str
    production_interpreter: PureWindowsPath
    launcher: PureWindowsPath
    principal: str
    principal_sid: str
    privilege: str
    semantic_arguments: tuple[()]
    scheduler_owned_environment: tuple[()]
    working_directory_is_authoritative: bool
    trigger_is_authoritative: bool
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


PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT = (
    PersonalDesktopUnattendedSchedulerContract(
        schema=PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA,
        production_interpreter=PureWindowsPath(r"F:\AITradingBot\runtime\python.exe"),
        launcher=PureWindowsPath(
            r"F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
            r"\run_personal_desktop_unattended_paper_operation.py"
        ),
        principal=r"DESKTOP-I4DOKM7\Trading",
        principal_sid="S-1-5-21-1397534616-3988210162-180023805-1009",
        privilege="NON_ADMIN_NON_ELEVATED",
        semantic_arguments=(),
        scheduler_owned_environment=(),
        working_directory_is_authoritative=False,
        trigger_is_authoritative=False,
        trigger_count_is_authoritative=False,
        next_run_time_is_authoritative=False,
        task_history_is_authoritative=False,
        previous_exit_is_authoritative=False,
        process_lifetime_is_authoritative=False,
        task_state_is_authoritative=False,
        overlap_policy_is_authoritative=False,
        authoritative_overlap_control="PD2A_ACCOUNT_MUTEX",
        timing_policy_is_frozen=False,
        installation_is_authorized=False,
        modification_is_authorized=False,
    )
)


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
