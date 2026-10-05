"""Focused pure Architecture-122 window and scheduler specification tests."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import PureWindowsPath
from zoneinfo import ZoneInfo

import pytest

from trading_bot.runtime import (
    personal_desktop_unattended_capture_warmup_scheduler_contract as d5_contract,
)
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as d10_contract,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_window import (
    OneWeekSoakState,
    build_one_week_soak_window,
)


def test_exact_seven_day_boundary_and_no_extension() -> None:
    activation = datetime(2026, 9, 23, 17, 12, 30, 123456, tzinfo=UTC)
    window = build_one_week_soak_window(activation)
    assert window.end_utc == datetime(2026, 9, 30, 17, 12, 30, 123456, tzinfo=UTC)
    assert window.state_at(activation) is OneWeekSoakState.ACTIVE
    assert (
        window.state_at(window.end_utc - timedelta(microseconds=1))
        is OneWeekSoakState.ACTIVE
    )
    assert window.state_at(window.end_utc) is OneWeekSoakState.EXPIRED
    assert (
        window.state_at(window.end_utc + timedelta(microseconds=1))
        is OneWeekSoakState.EXPIRED
    )
    assert (
        window.state_at(activation - timedelta(microseconds=1))
        is OneWeekSoakState.EXPIRED
    )
    with pytest.raises(ValueError):
        replace(window, end_utc=window.end_utc + timedelta(seconds=1))


@pytest.mark.parametrize("value", [datetime(2026, 9, 23), "2026-09-23", None])
def test_aware_datetime_is_required(value: object) -> None:
    with pytest.raises(ValueError):
        build_one_week_soak_window(value)  # type: ignore[arg-type]
    window = build_one_week_soak_window(datetime(2026, 9, 23, tzinfo=UTC))
    with pytest.raises(ValueError):
        window.state_at(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("local", "expected_utc"),
    [
        (
            datetime(2026, 3, 7, 12, tzinfo=ZoneInfo("America/Los_Angeles")),
            datetime(2026, 3, 14, 20, tzinfo=UTC),
        ),
        (
            datetime(2026, 10, 31, 12, tzinfo=ZoneInfo("America/Los_Angeles")),
            datetime(2026, 11, 7, 19, tzinfo=UTC),
        ),
    ],
)
def test_dst_uses_exact_utc_seven_day_instant(
    local: datetime, expected_utc: datetime
) -> None:
    window = build_one_week_soak_window(local)
    assert window.activation_utc == local.astimezone(UTC)
    assert window.end_utc == expected_utc
    assert window.end_utc - window.activation_utc == timedelta(days=7)
    assert (
        window.state_at(expected_utc.astimezone(ZoneInfo("America/Los_Angeles")))
        is OneWeekSoakState.EXPIRED
    )


def test_d10_contract_diff_is_exact_and_zero_semantic_arguments() -> None:
    d5 = d5_contract.personal_desktop_unattended_capture_warmup_scheduler_contract()
    d10 = d10_contract.one_week_soak_scheduler_contract()
    changed = {
        field.name
        for field in fields(d5)
        if getattr(d5, field.name) != getattr(d10, field.name)
    }
    assert changed == {
        "schema",
        "interpreter_arguments",
        "launcher",
        "working_directory",
    }
    assert d10_contract.is_frozen_one_week_soak_scheduler_contract(d10)
    assert not d10_contract.is_frozen_one_week_soak_scheduler_contract(
        replace(d10, restart_count=1)
    )
    assert d10.launcher == d10_contract.D10_LAUNCH_GUARD
    assert d10.production_interpreter == PureWindowsPath(
        r"F:\AITradingBot\runtime\python.exe"
    )
    assert d10.principal.endswith(r"\Trading")
    assert d10.run_level == "LeastPrivilege"
    assert d10.task_scheduler_run_level == "LUA"
    assert d10.semantic_arguments == ()
    assert d10.interpreter_arguments == d10_contract.D10_INTERPRETER_ARGUMENTS
    assert d10.restart_on_failure is False
    assert d10.restart_count == 0
    assert d10.multiple_instances_policy == "IgnoreNew"


def test_deployment_spec_bounds_trigger_at_exact_end() -> None:
    activation = datetime(2026, 3, 7, 20, tzinfo=UTC)
    spec = d10_contract.build_one_week_soak_scheduler_deployment_spec(activation)
    assert spec.window.end_utc == activation + timedelta(days=7)
    assert spec.end_boundary.astimezone(UTC) == spec.window.end_utc
    assert spec.task.start_boundary.astimezone(UTC) > activation
    assert spec.task.start_boundary.astimezone(UTC) < spec.window.end_utc
    assert spec.task.arguments == d10_contract.D10_GUARD_ARGUMENTS
    assert spec.task.semantic_arguments == ()
    assert spec.task.working_directory == d10_contract.D10_ROOT
    assert spec.task.scheduler_owned_environment == ()
    assert spec.task.start_when_available
    with pytest.raises(ValueError):
        replace(spec, end_boundary=spec.end_boundary + timedelta(seconds=1))
    with pytest.raises(ValueError):
        replace(spec, end_boundary=spec.window.end_utc)
    with pytest.raises(ValueError):
        replace(spec, task=replace(spec.task, principal="wrong"))
    with pytest.raises(ValueError):
        replace(spec, task=replace(spec.task, arguments=("-I", "wrong")))


def test_sealed_d10_paths_and_exact_two_stage_commands() -> None:
    assert str(d10_contract.D10_ROOT) == r"F:\AITradingBot\D10"
    assert str(d10_contract.D10_SOURCE_ROOT) == r"F:\AITradingBot\D10\source"
    assert str(d10_contract.D10_LAUNCH_GUARD) == r"F:\AITradingBot\D10\launch-guard.py"
    assert str(d10_contract.D10_CACHE_PREFIX) == r"F:\AITradingBot\D10\no-pycache"
    assert d10_contract.D10_GUARD_SOURCE_RELATIVE_PATH == (
        "scripts/run_personal_desktop_d10_launch_guard.py"
    )
    assert d10_contract.D10_LAUNCHER_SOURCE_RELATIVE_PATH == (
        "scripts/run_personal_desktop_unattended_one_week_soak.py"
    )
    assert d10_contract.D10_GUARD_ARGUMENTS == (
        "-I",
        "-S",
        "-B",
        "-X",
        r"pycache_prefix=F:\AITradingBot\D10\no-pycache",
        r"F:\AITradingBot\D10\launch-guard.py",
    )
    assert d10_contract.D10_SECOND_STAGE_ARGUMENTS == (
        "-I",
        "-S",
        "-B",
        "-X",
        r"pycache_prefix=F:\AITradingBot\D10\no-pycache",
        r"F:\AITradingBot\D10\source\scripts\run_personal_desktop_unattended_one_week_soak.py",
    )
    assert (
        d10_contract.D10_SCHEDULER_CONTRACT.working_directory == d10_contract.D10_ROOT
    )
    assert r"F:\AI\worktrees" not in " ".join(d10_contract.D10_GUARD_ARGUMENTS)
    assert r"F:\AI\worktrees" not in " ".join(d10_contract.D10_SECOND_STAGE_ARGUMENTS)


def test_direct_window_model_rejects_non_utc_fields() -> None:
    local = datetime(2026, 9, 23, 12, tzinfo=ZoneInfo("America/Los_Angeles"))
    window = build_one_week_soak_window(local)
    with pytest.raises(ValueError):
        replace(window, activation_utc=local)
