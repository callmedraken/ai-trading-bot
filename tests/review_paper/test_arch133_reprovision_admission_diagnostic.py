"""133-R source-only staged admission diagnostic tests."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.arch133_reprovision_diagnostic import operator

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def admitted(monkeypatch):
    material = SimpleNamespace()
    material.activation = object()
    material.host = SimpleNamespace(to_json=lambda: "{}")
    monkeypatch.setattr(operator, "read_material", lambda path: material)
    monkeypatch.setattr(
        operator, "_observe_predecessor", lambda: ("old", {"runtime": {}})
    )
    monkeypatch.setattr(operator, "_require_retained", lambda old: None)
    monkeypatch.setattr(operator, "require_stale", lambda old, now: None)
    monkeypatch.setattr(
        operator, "require_fresh", lambda material, old, runtime, now: {}
    )
    monkeypatch.setattr(operator.namespace, "require_vacant", lambda: None)
    monkeypatch.setattr(operator, "_parent", lambda path: None)

    @contextmanager
    def guard():
        yield {}

    monkeypatch.setattr(operator.namespace, "parent_guard", guard)
    return material


def _fail():
    raise ValueError("SECRET")


@pytest.mark.parametrize(
    "stage",
    [
        "MATERIAL_READ",
        "PREDECESSOR_ADMISSION",
        "PREDECESSOR_MATERIAL",
        "PREDECESSOR_STALE",
        "FRESH_MATERIAL",
        "NAMESPACE_VACANCY",
        "PARENT_VOLUME",
        "PARENT_HOST",
        "PARENT_COMBINED",
    ],
)
def test_each_stage_fails_closed_with_zero_effects(
    admitted, monkeypatch, tmp_path, stage
):
    if stage == "MATERIAL_READ":
        monkeypatch.setattr(operator, "read_material", lambda path: _fail())
    elif stage == "PREDECESSOR_ADMISSION":
        monkeypatch.setattr(operator, "_observe_predecessor", _fail)
    elif stage == "PREDECESSOR_MATERIAL":
        monkeypatch.setattr(operator, "_require_retained", lambda old: _fail())
    elif stage == "PREDECESSOR_STALE":
        monkeypatch.setattr(operator, "require_stale", lambda old, now: _fail())
    elif stage == "FRESH_MATERIAL":
        monkeypatch.setattr(
            operator, "require_fresh", lambda material, old, runtime, now: _fail()
        )
    elif stage == "NAMESPACE_VACANCY":
        monkeypatch.setattr(operator.namespace, "require_vacant", _fail)
    elif stage in {"PARENT_VOLUME", "PARENT_HOST"}:
        target = "F:\\" if stage == "PARENT_VOLUME" else r"F:\AITradingBot"

        def parent(path):
            if path == target:
                _fail()

        monkeypatch.setattr(operator, "_parent", parent)
    else:

        @contextmanager
        def bad_guard():
            _fail()
            yield {}

        monkeypatch.setattr(operator.namespace, "parent_guard", bad_guard)

    result = operator.diagnose(tmp_path / "material.json")
    assert result["status"] == "BLOCKED"
    assert result["stage"] == stage
    assert "SECRET" not in json.dumps(result)
    assert all(result[name] == 0 for name in operator.ZERO_EFFECTS)


def test_complete_diagnostic_is_effect_free(admitted, tmp_path):
    result = operator.diagnose(tmp_path / "material.json")
    assert result["status"] == "PASS"
    assert result["stage"] == "ADMISSION_COMPLETE"
    assert all(result[name] == 0 for name in operator.ZERO_EFFECTS)


def test_fresh_import_closure_has_no_reprovision_writer_or_effect_surface(tmp_path):
    source = (
        "import sys,json;sys.path.insert(0,sys.argv[1]);"
        "import trading_bot.arch133_reprovision_diagnostic.operator;"
        "print(json.dumps(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", source, str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    imported = json.loads(result.stdout)
    for name in imported:
        assert not name.startswith(
            (
                "trading_bot.arch133_reprovision.native",
                "trading_bot.review_paper.unattended_host",
                "trading_bot.review_paper.unattended_execution",
                "trading_bot.robinhood_mcp",
            )
        )


def test_diagnostic_source_has_no_mutation_or_effect_entrypoints():
    source = (
        ROOT / "src/trading_bot/arch133_reprovision_diagnostic/operator.py"
    ).read_text(encoding="utf-8")
    launcher = (
        ROOT / "scripts/run_arch133_reprovision_admission_diagnostic.py"
    ).read_text(encoding="utf-8")
    combined = source + launcher
    for forbidden in (
        "WindowsEdges",
        "execute-once",
        "SetFileInformationByHandle",
        "CreateDirectoryW",
        "SetSecurityInfo",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "WindowsOAuthStorage",
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
    ):
        assert forbidden not in combined


def test_runner_registers_source_only_successor():
    from scripts import checkpoint_runner as runner

    name = "arch133-robinhood-reprovision-admission-diagnostic"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133r"
    assert spec.tests == (
        *runner.ARCH133_L_M_TESTS,
        "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_L_M_RUFF_PATHS,
        *runner.ARCH133_REPROVISION_DIAGNOSTIC_SOURCES,
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS[-2:] == (
        "arch133-robinhood-fresh-activation-reprovision",
        name,
    )
