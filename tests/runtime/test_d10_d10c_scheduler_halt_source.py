from __future__ import annotations

from pathlib import Path

HALT = Path(__file__).resolve().parents[2] / "scripts" / "d10_d10c_scheduler_halt.ps1"


def test_d10c_scheduler_halt_is_fixed_disable_only() -> None:
    source = HALT.read_text(encoding="utf-8")

    required = (
        "AITradingBot-PD4-UnattendedPaper-v1",
        "F:\\AITradingBot\\runtime\\python.exe",
        "F:\\AITradingBot\\D10\\launch-guard.py",
        "2026-09-29T01:30:00-07:00",
        "2026-10-05T17:45:22-07:00",
        "$task.Enabled = $false",
        "DISABLED_VERIFIED",
    )
    for token in required:
        assert token in source

    forbidden = (
        "RegisterTaskDefinition",
        ".Run(",
        ".Stop(",
        ".DeleteTask(",
        "schtasks",
        "Register-ScheduledTask",
        "Disable-ScheduledTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        "Remove-ScheduledTask",
        "Set-ScheduledTask",
    )
    for token in forbidden:
        assert token not in source


def test_d10c_scheduler_halt_reuses_independent_observer_and_checks_two_reads() -> None:
    source = HALT.read_text(encoding="utf-8")
    assert "d10_p1245_scheduler_observe.ps1" in source
    assert source.count("Read-FixedTask $folder") == 4
    assert "Require-ExactSemantics $second $true" in source
    assert "Require-ExactSemantics $fourth $false" in source
    assert "[int]$task.State -eq 4" in source
    assert "[int]$postTask.State -eq 4" in source
