"""Focused O2 source-checkout launcher isolation coverage."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_operator_snapshot_launcher_is_checkout_and_cwd_independent(
    tmp_path: Path,
) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    (
        alternate_cli / "pd4_operator_observability_snapshot.py"
    ).write_text(
        "def main(argv=None):\n"
        "    print('alternate operator package selected')\n"
        "    return 73\n"
    )

    away = tmp_path / "away-from-repository"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = (
        _ROOT
        / "scripts"
        / "run_personal_desktop_operator_observability_snapshot.py"
    )
    expected = "Read one effects-closed PD4 operator observability snapshot."

    for command in (
        [sys.executable, "-I", str(script), "--help"],
        [sys.executable, str(script), "--help"],
    ):
        completed = subprocess.run(
            command,
            cwd=away,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert expected in completed.stdout
        assert "alternate operator package selected" not in completed.stdout
        assert completed.stderr == ""


def test_operator_snapshot_launcher_has_no_direct_effect_root() -> None:
    paths = (
        _ROOT
        / "src"
        / "trading_bot"
        / "cli"
        / "pd4_operator_observability_snapshot.py",
        _ROOT
        / "scripts"
        / "run_personal_desktop_operator_observability_snapshot.py",
    )
    forbidden_calls = {
        "run_personal_desktop_unattended_market_data_capture",
        "WindowsEffectfulDailySnapshotCapture",
        "publish_personal_desktop_unattended_decision",
        "execute_personal_desktop_unattended_settlement",
        "execute_personal_desktop_unattended_paper_operation",
        "recover_personal_desktop_paper_operation_receipt_once",
        "provision_personal_desktop_paper_storage",
        "register_task",
        "run_task",
        "broker_order",
        "live_order",
    }
    called: set[str] = set()
    assigned: set[str] = set()

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called.update(
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        )
        assigned.update(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        )

    assert "read_personal_desktop_operator_observability_snapshot" in called
    assert called.isdisjoint(forbidden_calls)
    assert not any(name.endswith("EFFECTS_ENABLED") for name in assigned)
