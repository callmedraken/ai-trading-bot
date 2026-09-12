"""Focused pure PD4-E scheduler-contract coverage."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, replace
from hashlib import sha1
from pathlib import Path, PureWindowsPath

import pytest

from trading_bot.runtime import personal_desktop_paper_account_publication_freeze
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT,
    PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA,
    is_frozen_personal_desktop_unattended_scheduler_contract,
    personal_desktop_unattended_scheduler_contract,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_exact_source_owned_scheduler_action_and_principal_are_frozen() -> None:
    contract = personal_desktop_unattended_scheduler_contract()
    assert contract is PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.schema == PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA
    assert contract.production_interpreter == PureWindowsPath(
        r"F:\AITradingBot\runtime\python.exe"
    )
    assert contract.launcher == PureWindowsPath(
        r"F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
        r"\run_personal_desktop_unattended_paper_operation.py"
    )
    assert contract.principal == r"DESKTOP-I4DOKM7\Trading"
    assert contract.principal_sid == ("S-1-5-21-1397534616-3988210162-180023805-1009")
    assert contract.privilege == "NON_ADMIN_NON_ELEVATED"
    assert (
        tuple(
            inspect.signature(personal_desktop_unattended_scheduler_contract).parameters
        )
        == ()
    )
    assert is_frozen_personal_desktop_unattended_scheduler_contract(contract)
    with pytest.raises(FrozenInstanceError):
        contract.trigger_is_authoritative = True  # type: ignore[misc]


def test_scheduler_has_no_semantic_arguments_credentials_or_metadata_authority() -> (
    None
):
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.semantic_arguments == ()
    assert contract.scheduler_owned_environment == ()
    diagnostics_only = (
        contract.working_directory_is_authoritative,
        contract.trigger_is_authoritative,
        contract.trigger_count_is_authoritative,
        contract.next_run_time_is_authoritative,
        contract.task_history_is_authoritative,
        contract.previous_exit_is_authoritative,
        contract.process_lifetime_is_authoritative,
        contract.task_state_is_authoritative,
    )
    assert diagnostics_only == (False,) * len(diagnostics_only)
    for field in (
        "working_directory_is_authoritative",
        "trigger_is_authoritative",
        "trigger_count_is_authoritative",
        "next_run_time_is_authoritative",
        "task_history_is_authoritative",
        "previous_exit_is_authoritative",
        "process_lifetime_is_authoritative",
        "task_state_is_authoritative",
    ):
        assert not is_frozen_personal_desktop_unattended_scheduler_contract(
            replace(contract, **{field: True})
        )


def test_overlap_and_future_effect_boundaries_remain_explicit() -> None:
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.overlap_policy_is_authoritative is False
    assert contract.authoritative_overlap_control == "PD2A_ACCOUNT_MUTEX"
    assert contract.timing_policy_is_frozen is False
    assert contract.installation_is_authorized is False
    assert contract.modification_is_authorized is False


def test_contract_source_has_no_task_install_or_external_effect_callable() -> None:
    path = (
        _ROOT
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_unattended_scheduler_contract.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported.isdisjoint(
        {
            "subprocess",
            "win32com.client",
            "trading_bot.market_data",
            "trading_bot.broker",
        }
    )
    forbidden = {
        "schtasks",
        "register_task",
        "create_task",
        "modify_task",
        "run_task",
        "provider_call",
        "recover_paper_operation_receipt_once",
        "execute_paper_operation_once",
        "broker_order",
        "live_order",
    }
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert called.isdisjoint(forbidden)


def test_personal_desktop_publication_freeze_remains_unchanged() -> None:
    payload = Path(
        personal_desktop_paper_account_publication_freeze.__file__
    ).read_bytes()
    blob = b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    assert (
        sha1(blob, usedforsecurity=False).hexdigest()
        == "b125cbb1c80a827f74018cf2955b9a27ba69fa90"
    )
