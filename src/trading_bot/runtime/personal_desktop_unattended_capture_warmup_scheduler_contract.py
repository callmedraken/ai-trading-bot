"""Pure Architecture-112 D5 scheduler-action contract.

The existing D2 task remains an untrusted zero-argument wake source. D5 changes
only the reviewed source launcher action, and actual Task Scheduler mutation
remains a separate operator effect checkpoint.
"""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import PureWindowsPath

from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    PersonalDesktopUnattendedSchedulerContract,
    is_frozen_personal_desktop_unattended_scheduler_contract,
    personal_desktop_unattended_scheduler_contract,
)

PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT_SCHEMA = (
    "personal-desktop-unattended-capture-warmup-scheduler-contract/v1"
)
PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_LAUNCHER = PureWindowsPath(
    r"F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
    r"\run_personal_desktop_unattended_capture_warmup.py"
)

_D2_CONTRACT = personal_desktop_unattended_scheduler_contract()

PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT = replace(
    _D2_CONTRACT,
    schema=PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT_SCHEMA,
    launcher=PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_LAUNCHER,
    installation_is_authorized=False,
    modification_is_authorized=True,
    absent_task_disposition="BLOCKED",
    exact_existing_task_disposition="ACCEPT_READ_ONLY",
    conflicting_existing_task_disposition="BLOCKED",
)

_D5_ALLOWED_DIFFERENCES = frozenset(
    {
        "schema",
        "launcher",
        "installation_is_authorized",
        "modification_is_authorized",
        "absent_task_disposition",
        "conflicting_existing_task_disposition",
    }
)


def personal_desktop_unattended_capture_warmup_scheduler_contract() -> (
    PersonalDesktopUnattendedSchedulerContract
):
    """Return the fixed D5 scheduler-action target without scheduler I/O."""

    return PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT


def is_frozen_personal_desktop_unattended_capture_warmup_scheduler_contract(
    contract: object,
) -> bool:
    """Require the exact source-owned D5 contract value."""

    return (
        type(contract) is PersonalDesktopUnattendedSchedulerContract
        and contract == PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT
        and _differs_from_d2_only_as_reviewed(contract)
    )


def is_exact_d2_capture_warmup_predecessor(contract: object) -> bool:
    """Return whether an observed predecessor is the exact frozen D2 contract."""

    return is_frozen_personal_desktop_unattended_scheduler_contract(contract)


def _differs_from_d2_only_as_reviewed(
    contract: PersonalDesktopUnattendedSchedulerContract,
) -> bool:
    changed = {
        item.name
        for item in fields(PersonalDesktopUnattendedSchedulerContract)
        if getattr(contract, item.name) != getattr(_D2_CONTRACT, item.name)
    }
    return changed == _D5_ALLOWED_DIFFERENCES
