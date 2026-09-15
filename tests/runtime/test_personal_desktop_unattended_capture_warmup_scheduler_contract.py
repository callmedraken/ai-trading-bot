"""Focused Architecture-112 D5 scheduler-action contract coverage."""

from __future__ import annotations

from dataclasses import fields, replace

from trading_bot.runtime import (
    personal_desktop_unattended_capture_warmup_scheduler_contract as d5_contract,
)
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    PersonalDesktopUnattendedSchedulerContract,
    personal_desktop_unattended_scheduler_contract,
)

D5_LAUNCHER = d5_contract.PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_LAUNCHER
D5_SCHEMA = (
    d5_contract.PERSONAL_DESKTOP_UNATTENDED_CAPTURE_WARMUP_SCHEDULER_CONTRACT_SCHEMA
)
is_d2_predecessor = d5_contract.is_exact_d2_capture_warmup_predecessor
is_d5_contract = (
    d5_contract.is_frozen_personal_desktop_unattended_capture_warmup_scheduler_contract
)
get_d5_contract = d5_contract.personal_desktop_unattended_capture_warmup_scheduler_contract


def test_d5_contract_differs_from_d2_only_in_reviewed_action_metadata() -> None:
    d2 = personal_desktop_unattended_scheduler_contract()
    d5 = get_d5_contract()

    changed = {
        item.name
        for item in fields(PersonalDesktopUnattendedSchedulerContract)
        if getattr(d2, item.name) != getattr(d5, item.name)
    }

    assert changed == {
        "schema",
        "launcher",
        "installation_is_authorized",
        "modification_is_authorized",
        "absent_task_disposition",
    }
    assert d5.schema == D5_SCHEMA
    assert d5.launcher == D5_LAUNCHER
    assert d5.semantic_arguments == ()
    assert d5.scheduler_owned_environment == ()
    assert d5.installation_is_authorized is False
    assert d5.modification_is_authorized is True
    assert d5.absent_task_disposition == "BLOCKED"
    assert d5.exact_existing_task_disposition == "ACCEPT_READ_ONLY"
    assert d5.conflicting_existing_task_disposition == "BLOCKED"


def test_only_exact_d2_contract_is_valid_replacement_predecessor() -> None:
    d2 = personal_desktop_unattended_scheduler_contract()
    d5 = get_d5_contract()

    assert is_d2_predecessor(d2)
    assert not is_d2_predecessor(d5)
    assert not is_d2_predecessor(replace(d2, semantic_arguments=("--unsafe",)))


def test_d5_contract_validation_rejects_any_unreviewed_change() -> None:
    contract = get_d5_contract()

    assert is_d5_contract(contract)
    assert not is_d5_contract(
        replace(contract, working_directory_is_authoritative=True)
    )
