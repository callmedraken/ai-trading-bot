import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _EXPECTED_SERIAL,
    _FIXTURE_LEGACY,
    _fixture_profiles,
    _lane_names,
    _parser_arguments,
    _profile_inventory,
)


def test_protected_opt_in_presence_fails_closed() -> None:
    for name in runner.PROTECTED_OPT_INS:
        with pytest.raises(runner.CertificationError, match=name):
            runner.reject_protected_opt_ins({name: "0"})


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_plan_never_launches_pytest_and_saves_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    modules = _profile_inventory(tmp_path, profile)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(
        runner, "run_children", lambda *a: pytest.fail("pytest launched")
    )
    monkeypatch.setattr(
        runner, "run_static_checks", lambda *a: pytest.fail("static checks launched")
    )
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-plan-evidence",
        temp_root=tmp_path,
        profile=profile,
        plan=True,
    )
    result = runner.run(args)
    assert result["status"] == "planned"
    assert result["profile"] == profile
    assert result["repository_inventory"] == list(runner.discover_inventory(tmp_path))
    assert result["selected_inventory"] == result["inventory"] == sorted(modules)
    evidence = json.loads((args.evidence_dir / "inventory.json").read_text())
    assert evidence["profile"] == profile
    assert evidence["all"] == evidence["repository"] == result["repository_inventory"]
    assert evidence["selected"] == result["selected_inventory"]
    assert evidence["excluded"] == result["excluded_inventory"]
    assert set(evidence["selected"]) | set(evidence["excluded"]) == set(evidence["all"])
    assert set(evidence["selected"]).isdisjoint(evidence["excluded"])
    assert set(result["lanes"]) == set(_lane_names(profile))
    expected = _fixture_profiles()
    assert evidence["excluded"] == sorted(set(expected["exhaustive"]) - set(modules))
    assert evidence["classification"] == result["classification"]
    classification = evidence["classification"]
    assert classification["policy"] == "architecture-132-r1"
    assert classification["supported_inventory"] == list(expected["full"])
    assert classification["legacy_inventory"] == list(_FIXTURE_LEGACY)
    assert classification["profile_counts"] == {
        name: len(value) for name, value in expected.items()
    }
    assert (
        classification["ownership"]["supported_root_pattern"]
        == "tests/test_robinhood_*.py"
    )
    if profile == "exhaustive":
        assert evidence["selected"] == evidence["all"]
        assert evidence["excluded"] == []
    if profile in {"legacy", "exhaustive"}:
        assert evidence["serial"] == list(_EXPECTED_SERIAL)
        assert result["lanes"]["serial"]["module_count"] == 5
    else:
        assert evidence["serial"] == []
    assert (args.evidence_dir / "results.json").is_file()
    assert (args.evidence_dir / "inventory.json").is_file()


def test_failed_child_sets_failed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _profile_inventory(tmp_path, "full")
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(
        runner,
        "run_children",
        lambda *args: {
            "broad-1": {"error": "Child exited with 1", "exit_code": 1},
            "broad-2": {"exit_code": 0},
            "broad-3": {"exit_code": 0},
            "broad-4": {"exit_code": 0},
            "broad-5": {"exit_code": 0},
            "broad-6": {"exit_code": 0},
        },
    )
    monkeypatch.setattr(
        runner,
        "run_static_checks",
        lambda *args: {
            name: {"exit_code": 0}
            for name in ("ruff_version", "ruff_check", "ruff_format", "git_diff_check")
        },
    )
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / "evidence",
        temp_root=tmp_path,
        plan=False,
    )
    assert runner.run(args)["status"] == "failed"


def test_parser_defaults_to_full_and_rejects_unknown_profile() -> None:
    parser = runner.build_parser()
    assert parser.parse_args(_parser_arguments()).profile == "full"
    for profile in runner.PROFILES:
        assert (
            parser.parse_args(_parser_arguments() + ["--profile", profile]).profile
            == profile
        )
    with pytest.raises(SystemExit) as error:
        parser.parse_args(_parser_arguments() + ["--profile", "unknown"])
    assert error.value.code == 2
    with pytest.raises(runner.CertificationError, match="Unknown"):
        runner.select_inventory((), "unknown")


@pytest.mark.parametrize("profile", runner.PROFILES)
@pytest.mark.parametrize(
    "outcome", ["pass", "missing", "extra", "wrong", "error", "nonzero", "no_exit_code"]
)
def test_exact_profile_lane_success_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, outcome: str
) -> None:
    _profile_inventory(tmp_path, profile)
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    children = {name: {"exit_code": 0} for name in _lane_names(profile)}
    first = _lane_names(profile)[0]
    if outcome in {"missing", "wrong"}:
        children.pop(first)
    if outcome in {"extra", "wrong"}:
        children["unexpected"] = {"exit_code": 0}
    if outcome == "error":
        children[first]["error"] = "bad evidence"
    if outcome == "nonzero":
        children[first]["exit_code"] = 1
    if outcome == "no_exit_code":
        children[first] = {}
    monkeypatch.setattr(runner, "run_children", lambda *args: children)
    static_calls = []

    def static(*args):
        static_calls.append(True)
        return {
            name: {"exit_code": 0}
            for name in ("ruff_version", "ruff_check", "ruff_format", "git_diff_check")
        }

    monkeypatch.setattr(runner, "run_static_checks", static)
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-accounting",
        temp_root=tmp_path,
        profile=profile,
        plan=False,
    )
    result = runner.run(args)
    assert result["status"] == ("passed" if outcome == "pass" else "failed")
    assert static_calls == [True]


@pytest.mark.parametrize("profile", runner.PROFILES)
@pytest.mark.parametrize("name", runner.PROTECTED_OPT_INS)
def test_all_profiles_reject_protected_opt_ins_before_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, name: str
) -> None:
    monkeypatch.setenv(name, "0")
    monkeypatch.setattr(
        runner, "verify_source", lambda *a: pytest.fail("source verification ran")
    )
    args = argparse.Namespace(
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        profile=profile,
    )
    with pytest.raises(runner.CertificationError, match=name):
        runner.run(args)


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_static_checks_remain_whole_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    commands = []

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == tmp_path
        commands.append(command)
        return SimpleNamespace(
            returncode=0, stdout=f"ruff {runner.RUFF_VERSION}\n", stderr=""
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    args = argparse.Namespace(root=tmp_path, python=Path("python"), profile=profile)
    runner.run_static_checks(args, tmp_path)
    assert commands == [
        ["python", "-m", "ruff", "--version"],
        ["python", "-m", "ruff", "check", "--no-cache", "."],
        ["python", "-m", "ruff", "format", "--check", "--no-cache", "."],
        ["git", "diff", "--check"],
    ]


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_all_profiles_retain_temp_root_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    args = argparse.Namespace(
        root=tmp_path,
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        profile=profile,
        plan=False,
        temp_root=tmp_path,
    )
    with pytest.raises(runner.CertificationError, match="basetemp root"):
        runner.run(args)


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_github_actions_runner_temp_descendant_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _profile_inventory(tmp_path, profile)
    runner_temp = tmp_path.parent / f"{tmp_path.name}-runner-temp"
    runner_temp.mkdir()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(
        runner,
        "run_children",
        lambda *args: {name: {"exit_code": 0} for name in _lane_names(profile)},
    )
    monkeypatch.setattr(
        runner,
        "run_static_checks",
        lambda *args: {
            name: {"exit_code": 0}
            for name in ("ruff_version", "ruff_check", "ruff_format", "git_diff_check")
        },
    )
    args = SimpleNamespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=runner_temp / "evidence",
        temp_root=runner_temp / "pytest",
        plan=False,
        profile=profile,
    )

    summary = runner.run(args)

    assert summary["status"] == "passed"
    assert args.temp_root.is_dir()


def test_github_actions_temp_root_outside_runner_temp_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner_temp = tmp_path.parent / f"{tmp_path.name}-runner-temp"
    runner_temp.mkdir()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    args = SimpleNamespace(
        root=tmp_path,
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        profile="robinhood",
        plan=False,
        temp_root=tmp_path,
    )

    with pytest.raises(runner.CertificationError, match="RUNNER_TEMP"):
        runner.run(args)


@pytest.mark.parametrize(
    "outcome",
    ["pass", "nonzero", "timeout", "missing_junit", "malformed_junit", "cases"],
)
def test_six_child_totals_and_single_child_failure_fail_certification(
    tmp_path, monkeypatch, outcome
):
    _profile_inventory(tmp_path, "full")
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    children = {
        f"broad-{i}": {
            "exit_code": 0,
            "counts": dict(cases=i + 2, passed=i, skipped=2, failed=0, errors=0),
        }
        for i in range(1, 7)
    }
    if outcome != "pass":
        child = children["broad-6"]
        child["error"] = outcome
        if outcome == "nonzero":
            child["exit_code"] = 1
        if outcome == "cases":
            child["counts"].update(cases=10, failed=1, errors=1)
        if outcome in {"missing_junit", "malformed_junit"}:
            child.pop("counts")
    monkeypatch.setattr(runner, "run_children", lambda *args: children)
    monkeypatch.setattr(
        runner,
        "run_static_checks",
        lambda *args: {
            name: {"exit_code": 0}
            for name in ("ruff_version", "ruff_check", "ruff_format", "git_diff_check")
        },
    )
    args = SimpleNamespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-six-child-totals",
        temp_root=tmp_path,
        profile="full",
        plan=False,
    )
    summary = runner.run(args)
    assert summary["status"] == ("passed" if outcome == "pass" else "failed")
    expected = dict(cases=33, passed=21, skipped=12, failed=0, errors=0)
    if outcome == "cases":
        expected.update(cases=35, failed=1, errors=1)
    if outcome in {"missing_junit", "malformed_junit"}:
        expected.update(cases=25, passed=15, skipped=10)
    assert summary["totals"] == expected


@pytest.mark.parametrize(
    "actual,code",
    [
        ("ruff 0.17.3\n", 0),
        ("ruff 0.15.21\n", 0),
        ("ruff 0.17.30\n", 0),
        ("ruff 0.17.3 (unexpected)\n", 0),
        ("", 0),
        ("ruff 0.17.3\n", 1),
    ],
)
def test_exact_ruff_version_fails_closed(monkeypatch, tmp_path, actual, code):
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 30
        return SimpleNamespace(returncode=code, stdout=actual, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", execute)
    result = runner.check_ruff_version("python", tmp_path)
    assert result["expected"] == "ruff 0.17.3"
    assert result["actual"] == actual.strip()
    assert result["exit_code"] == (
        0 if actual.strip() == "ruff 0.17.3" and not code else 1
    )
    assert calls == [["python", "-m", "ruff", "--version"]]


@pytest.mark.parametrize(
    "error", [OSError("missing Ruff"), subprocess.TimeoutExpired("ruff", 30)]
)
def test_unavailable_ruff_stops_canonical_static_checks(monkeypatch, tmp_path, error):
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        raise error

    monkeypatch.setattr(runner.subprocess, "run", execute)
    result = runner.run_static_checks(
        SimpleNamespace(root=tmp_path, python="python"), tmp_path
    )
    assert set(result) == {"ruff_version"}
    assert result["ruff_version"]["exit_code"] == 1
    assert result["ruff_version"]["actual"] == "unavailable"
    assert len(calls) == 1
    assert (tmp_path / "ruff_version.stderr.log").read_text(encoding="utf-8")


def test_local_and_canonical_static_contract_is_identical(tmp_path):
    from scripts import checkpoint_runner as checkpoint

    root = Path(runner.__file__).resolve().parents[1]
    dev = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["optional-dependencies"]["dev"]
    assert [item for item in dev if item.startswith("ruff")] == ["ruff==0.17.3"]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert re.findall(r'"(ruff[^"]+)"', workflow) == ["ruff==0.17.3"] * 4
    assert runner.RUFF_VERSION == "0.17.3"
    assert checkpoint.check_ruff_version is runner.check_ruff_version
    assert checkpoint.CANONICAL_RUFF_ROOTS == runner.CANONICAL_RUFF_ROOTS == (".",)
    spec = checkpoint.CheckpointSpec(
        name=checkpoint.ARCH132_R3N_ADMISSION_NAME,
        description="parity",
        tests=("tests/example.py",),
        ruff_paths=checkpoint.ARCH132_R3N_ADMISSION_RUFF_PATHS,
        authority_check=lambda _: (),
    )
    steps = checkpoint.build_verification_steps(
        spec, python_executable="python", basetemp=tmp_path
    )
    local = {
        step.name: list(step.argv) for step in steps if step.name.startswith("ruff")
    }
    assert (
        local
        == runner.canonical_ruff_commands("python")
        == {
            "ruff_check": ["python", "-m", "ruff", "check", "--no-cache", "."],
            "ruff_format": [
                "python",
                "-m",
                "ruff",
                "format",
                "--check",
                "--no-cache",
                ".",
            ],
        }
    )


def test_canonical_formatter_reads_acquisition_validation_plan():
    root = Path(runner.__file__).resolve().parents[1]
    path = "docs/validation/arch146-b-historical-research-acquisition-custody-plan.md"
    (root / path).read_bytes().decode("utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--no-cache", path],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "failure",
    [None, "ruff_version", "ruff_check", "ruff_format", "git_diff_check", "missing"],
)
def test_static_gate_precedes_children_and_persists_evidence(
    tmp_path, monkeypatch, failure
):
    _profile_inventory(tmp_path, "full")
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    events = []

    def source(args):
        events.append("source")
        return {"head": "h", "tree": "t"}

    def static(*args):
        events.append("static")
        results = {
            name: {"exit_code": int(name == failure)}
            for name in ("ruff_version", "ruff_check", "ruff_format", "git_diff_check")
        }
        if failure == "missing":
            results.pop("ruff_format")
        return results

    def children(args, lanes, evidence):
        if failure:
            pytest.fail("pytest child started after static failure")
        events.append("children")
        return {name: {"exit_code": 0} for name in lanes}

    monkeypatch.setattr(runner, "verify_source", source)
    monkeypatch.setattr(runner, "run_static_checks", static)
    monkeypatch.setattr(runner, "run_children", children)
    args = SimpleNamespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        temp_root=tmp_path,
        plan=False,
        profile="full",
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-static-evidence",
    )
    result = runner.run(args)
    assert events == (
        ["source", "static", "source"]
        if failure
        else ["source", "static", "children", "source", "source"]
    )
    assert result["status"] == ("failed" if failure else "passed")
    assert result["final_source"] == {"head": "h", "tree": "t"}
    assert json.loads((args.evidence_dir / "results.json").read_text()) == result
    assert (args.evidence_dir / "inventory.json").is_file()
    if failure:
        assert result["children"] == {}
        assert result["totals"] == dict(
            cases=0, passed=0, skipped=0, failed=0, errors=0
        )
        assert "post_test_source" not in result


@pytest.mark.parametrize(
    "path", ["pyproject.toml", ".github/workflows/checkpoint-source-gates.yml"]
)
def test_current_toolchain_owner_rejects_version_drift(tmp_path, path):
    root = Path(runner.__file__).resolve().parents[1]
    for relative in ("pyproject.toml", ".github/workflows/checkpoint-source-gates.yml"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = (root / relative).read_text(encoding="utf-8")
        if relative == path:
            text = text.replace("ruff==0.17.3", "ruff>=0.6,<1.0")
        destination.write_text(text, encoding="utf-8")
    assert runner.static_toolchain_contract_failures(root) == ()
    assert runner.static_toolchain_contract_failures(tmp_path)
