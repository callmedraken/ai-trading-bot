import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _EXPECTED_FULL,
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
    assert classification["supported_inventory"] == list(_EXPECTED_FULL)
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
        },
    )
    monkeypatch.setattr(
        runner, "run_static_checks", lambda *args: pytest.fail("static checks ran")
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
            for name in ("ruff_check", "ruff_format", "git_diff_check")
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
    assert bool(static_calls) == (outcome == "pass")


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
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    args = argparse.Namespace(root=tmp_path, python=Path("python"), profile=profile)
    runner.run_static_checks(args, tmp_path)
    assert commands == [
        ["python", "-m", "ruff", "check", "--no-cache", "."],
        ["python", "-m", "ruff", "format", "--check", "--no-cache", "."],
        ["git", "diff", "--check"],
    ]


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_all_profiles_retain_temp_root_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
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
