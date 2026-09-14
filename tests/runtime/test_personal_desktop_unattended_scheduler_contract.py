"""Focused pure PD4-D2 scheduler contract and deployment-spec coverage."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, asdict, fields, replace
from datetime import UTC, datetime, time
from hashlib import sha1
from pathlib import Path, PureWindowsPath
from zoneinfo import ZoneInfo

import pytest

from trading_bot.runtime import personal_desktop_paper_account_publication_freeze
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT,
    PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA,
    PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA,
    PersonalDesktopUnattendedSchedulerContract,
    PersonalDesktopUnattendedSchedulerDeploymentSpec,
    build_personal_desktop_unattended_scheduler_deployment_spec,
    is_frozen_personal_desktop_unattended_scheduler_contract,
    personal_desktop_unattended_scheduler_contract,
)

_ROOT = Path(__file__).resolve().parents[2]
_PACIFIC = ZoneInfo("America/Los_Angeles")


def test_exact_source_owned_scheduler_identity_action_and_principal_are_frozen() -> (
    None
):
    contract = personal_desktop_unattended_scheduler_contract()
    assert contract is PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.schema == "personal-desktop-unattended-scheduler-contract/v2"
    assert contract.schema == PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT_SCHEMA
    assert contract.task_path == r"\AITradingBot-PD4-UnattendedPaper-v1"
    assert contract.production_interpreter == PureWindowsPath(
        r"F:\AITradingBot\runtime\python.exe"
    )
    assert contract.interpreter_arguments == ("-I",)
    assert contract.launcher == PureWindowsPath(
        r"F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
        r"\run_personal_desktop_unattended_paper_operation.py"
    )
    assert contract.semantic_arguments == ()
    assert contract.working_directory == PureWindowsPath(
        r"F:\AI\worktrees\ai-trading-bot-personal-desktop"
    )
    assert contract.scheduler_owned_environment == ()
    assert contract.principal == r"DESKTOP-I4DOKM7\Trading"
    assert contract.principal_sid == "S-1-5-21-1397534616-3988210162-180023805-1009"
    assert contract.logon_type == "Password"
    assert contract.run_level == "LeastPrivilege"
    assert contract.task_scheduler_run_level == "LUA"
    assert (
        tuple(
            inspect.signature(personal_desktop_unattended_scheduler_contract).parameters
        )
        == ()
    )
    assert is_frozen_personal_desktop_unattended_scheduler_contract(contract)
    with pytest.raises(FrozenInstanceError):
        contract.task_path = "changed"  # type: ignore[misc]


def test_exact_daily_trigger_and_task_settings_are_frozen() -> None:
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.trigger_type == "DAILY"
    assert contract.host_timezone == "Pacific Standard Time"
    assert contract.source_timezone == "America/Los_Angeles"
    assert contract.local_wall_clock_time == time(1, 30)
    assert contract.days_interval == 1
    assert contract.start_when_available is True
    assert contract.random_delay is None
    assert contract.repetition is None
    assert contract.enabled is True
    assert contract.allow_start_on_demand is True
    assert contract.wake_to_run is True
    assert contract.run_only_if_idle is False
    assert contract.run_only_if_network_available is False
    assert contract.disallow_start_if_on_batteries is False
    assert contract.stop_if_going_on_batteries is False
    assert contract.hidden is False
    assert contract.multiple_instances_policy == "IgnoreNew"
    assert contract.restart_on_failure is False
    assert contract.restart_count == 0
    assert contract.execution_time_limit == "PT1H"
    assert contract.priority == 7


def test_scheduler_diagnostics_and_overlap_remain_non_authoritative() -> None:
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    diagnostics_only = (
        contract.working_directory_is_authoritative,
        contract.trigger_is_authoritative,
        contract.trigger_occurrence_is_authoritative,
        contract.trigger_count_is_authoritative,
        contract.next_run_time_is_authoritative,
        contract.task_history_is_authoritative,
        contract.previous_exit_is_authoritative,
        contract.process_lifetime_is_authoritative,
        contract.task_state_is_authoritative,
        contract.overlap_policy_is_authoritative,
    )
    assert diagnostics_only == (False,) * len(diagnostics_only)
    assert contract.authoritative_overlap_control == "PD2A_ACCOUNT_MUTEX"
    for field_name in (
        "working_directory_is_authoritative",
        "trigger_is_authoritative",
        "trigger_occurrence_is_authoritative",
        "trigger_count_is_authoritative",
        "next_run_time_is_authoritative",
        "task_history_is_authoritative",
        "previous_exit_is_authoritative",
        "process_lifetime_is_authoritative",
        "task_state_is_authoritative",
        "overlap_policy_is_authoritative",
    ):
        assert not is_frozen_personal_desktop_unattended_scheduler_contract(
            replace(contract, **{field_name: True})
        )


def test_installation_policy_approves_create_but_not_modification() -> None:
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert contract.timing_policy_is_frozen is True
    assert contract.installation_is_authorized is True
    assert contract.modification_is_authorized is False
    assert contract.installation_requires_separate_operator_effect_checkpoint is True
    assert contract.absent_task_disposition == "CREATE_AT_OPERATOR_EFFECT_CHECKPOINT"
    assert contract.exact_existing_task_disposition == "ACCEPT_READ_ONLY"
    assert contract.conflicting_existing_task_disposition == "BLOCKED"


def test_deployment_spec_is_exact_and_has_no_secret_field() -> None:
    observed = datetime(2026, 7, 6, 1, 29, 59, tzinfo=_PACIFIC)
    spec = build_personal_desktop_unattended_scheduler_deployment_spec(observed)
    contract = PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_CONTRACT
    assert spec.schema == PERSONAL_DESKTOP_UNATTENDED_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA
    assert spec.task_path == contract.task_path
    assert spec.principal == contract.principal
    assert spec.principal_sid == contract.principal_sid
    assert spec.logon_type == "Password"
    assert spec.run_level == "LeastPrivilege"
    assert spec.task_scheduler_run_level == "LUA"
    assert spec.executable == contract.production_interpreter
    assert spec.arguments == ("-I", str(contract.launcher))
    assert spec.semantic_arguments == ()
    assert spec.scheduler_owned_environment == ()
    assert spec.working_directory == contract.working_directory
    assert spec.host_timezone == "Pacific Standard Time"
    assert spec.start_boundary == datetime(2026, 7, 6, 1, 30, tzinfo=_PACIFIC)
    assert spec.start_boundary > observed
    assert spec.days_interval == 1
    assert spec.start_when_available is True
    assert spec.restart_count == 0
    assert spec.multiple_instances_policy == "IgnoreNew"
    assert spec.execution_time_limit == "PT1H"
    assert spec.priority == 7
    for model in (
        PersonalDesktopUnattendedSchedulerContract,
        PersonalDesktopUnattendedSchedulerDeploymentSpec,
    ):
        assert all(item.name.casefold() != "password" for item in fields(model))
    assert "credential" not in repr(spec).casefold()
    assert "secret" not in repr(asdict(spec)).casefold()


def test_start_boundary_is_strictly_future_and_rolls_to_next_day() -> None:
    at_boundary = datetime(2026, 7, 6, 1, 30, tzinfo=_PACIFIC)
    spec = build_personal_desktop_unattended_scheduler_deployment_spec(at_boundary)
    assert spec.start_boundary == datetime(2026, 7, 7, 1, 30, tzinfo=_PACIFIC)


def test_start_boundary_uses_pacific_spring_dst_semantics() -> None:
    observed = datetime(2026, 3, 8, 10, 0, tzinfo=UTC)
    spec = build_personal_desktop_unattended_scheduler_deployment_spec(observed)
    assert spec.start_boundary == datetime(2026, 3, 9, 1, 30, tzinfo=_PACIFIC)
    assert spec.start_boundary.utcoffset().total_seconds() == -7 * 60 * 60


def test_start_boundary_uses_first_future_fall_dst_occurrence() -> None:
    before_both = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    first = build_personal_desktop_unattended_scheduler_deployment_spec(before_both)
    assert first.start_boundary.fold == 0
    assert first.start_boundary.astimezone(UTC) == datetime(
        2026, 11, 1, 8, 30, tzinfo=UTC
    )

    between_occurrences = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    second = build_personal_desktop_unattended_scheduler_deployment_spec(
        between_occurrences
    )
    assert second.start_boundary.fold == 1
    assert second.start_boundary.astimezone(UTC) == datetime(
        2026, 11, 1, 9, 30, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "observed",
    (datetime(2026, 7, 6, 1, 0), "2026-07-06T01:00:00"),
)
def test_start_boundary_rejects_non_aware_datetime(observed: object) -> None:
    with pytest.raises(ValueError, match="aware datetime"):
        build_personal_desktop_unattended_scheduler_deployment_spec(observed)  # type: ignore[arg-type]


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
            "os",
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
