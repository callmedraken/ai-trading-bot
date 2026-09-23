"""Focused contract tests for the persistent certification runner."""

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner


def _inventory(tmp_path: Path) -> tuple[str, ...]:
    modules = (
        "tests/a/test_first.py",
        "tests/a/test_second.py",
        "tests/b/test_third.py",
        "tests/b/test_fourth.py",
        "tests/safety/test_serial.py",
    )
    for index, module in enumerate(modules):
        path = tmp_path / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (index + 1))
    return modules


def test_inventory_partition_is_complete_disjoint_and_deterministic(
    tmp_path: Path,
) -> None:
    modules = _inventory(tmp_path)
    inventory = runner.discover_inventory(tmp_path)
    assert inventory == tuple(sorted(modules))
    broad, serial = runner.separate_serial(inventory, ("tests/safety/test_serial.py",))
    lanes = runner.balance_broad(tmp_path, broad)
    assert lanes == runner.balance_broad(tmp_path, broad)
    runner.validate_partitions(inventory, (*lanes, serial))
    assert set(lanes[0]).isdisjoint(lanes[1])
    assert set(lanes[0] + lanes[1] + serial) == set(modules)


def test_missing_serial_and_duplicate_or_overlap_fail(tmp_path: Path) -> None:
    inventory = runner.discover_inventory(tmp_path)
    with pytest.raises(runner.CertificationError, match="Missing serial"):
        runner.separate_serial(inventory, ("tests/missing/test_serial.py",))
    with pytest.raises(runner.CertificationError, match="Duplicate"):
        runner.validate_partitions(("a", "b"), (("a",), ("a", "b")))
    with pytest.raises(runner.CertificationError, match="Incomplete"):
        runner.validate_partitions(("a", "b"), (("a",), ()))


@pytest.mark.parametrize(
    "xml", ["", "<testsuites/>", "<testsuite><testcase name='x'>", "<other/>"]
)
def test_empty_or_malformed_junit_fails(tmp_path: Path, xml: str) -> None:
    path = tmp_path / "result.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(runner.CertificationError):
        runner.parse_junit(path)


@pytest.mark.parametrize("outcome", ["failure", "error"])
def test_failed_or_error_testcase_fails(tmp_path: Path, outcome: str) -> None:
    path = tmp_path / "result.xml"
    path.write_text(
        f"<testsuite><testcase name='bad'><{outcome}/></testcase></testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(runner.CertificationError, match="failed/error"):
        runner.parse_junit(path)


def test_skipped_is_counted_separately(tmp_path: Path) -> None:
    path = tmp_path / "result.xml"
    path.write_text(
        "<testsuites><testsuite tests='2' skipped='1' failures='0' errors='0'>"
        "<testcase name='ok'/><testcase name='skip'><skipped/></testcase>"
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert runner.parse_junit(path) == {
        "cases": 2,
        "passed": 1,
        "skipped": 1,
        "failed": 0,
        "errors": 0,
    }


def test_protected_opt_in_presence_fails_closed() -> None:
    for name in runner.PROTECTED_OPT_INS:
        with pytest.raises(runner.CertificationError, match=name):
            runner.reject_protected_opt_ins({name: "0"})


def test_subprocess_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailedProcess:
        returncode = 7

        def wait(self, timeout: int) -> int:
            return self.returncode

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: FailedProcess())
    monkeypatch.setattr(
        runner,
        "parse_junit",
        lambda path, **kwargs: {
            "cases": 1,
            "passed": 1,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
    )
    args = SimpleNamespace(
        root=tmp_path, python=Path("python"), temp_root=tmp_path, timeout_seconds=1
    )
    result = runner.run_children(
        args, {"broad-1": ("tests/a/test_first.py",)}, tmp_path
    )
    assert result["broad-1"]["exit_code"] == 7
    assert "error" in result["broad-1"]


def test_plan_never_launches_pytest_and_saves_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _inventory(tmp_path)
    monkeypatch.setattr(runner, "SERIAL_MODULES", ("tests/safety/test_serial.py",))
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(
        runner, "run_children", lambda *a: pytest.fail("pytest launched")
    )
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / "plan-evidence",
        temp_root=tmp_path,
        plan=True,
    )
    result = runner.run(args)
    assert result["status"] == "planned"
    assert len(result["inventory"]) == len(modules)
    assert result["lanes"]["serial"]["module_count"] == 1
    assert (args.evidence_dir / "results.json").is_file()
    assert (args.evidence_dir / "inventory.json").is_file()


def test_source_identity_mismatch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        return {
            ("branch", "--show-current"): "feature/actual",
            ("rev-parse", "HEAD"): "head",
            ("show", "-s", "--format=%T", "HEAD"): "tree",
            ("rev-parse", "origin/develop"): "base",
        }[arguments]

    monkeypatch.setattr(runner, "_git", fake_git)
    monkeypatch.setattr(runner, "_resolve_live_origin_branch_sha", lambda *a: "base")
    args = argparse.Namespace(
        root=tmp_path,
        expected_head="head",
        expected_tree="tree",
        expected_base_head="base",
        expected_branch="feature/expected",
        expected_feature_ref=None,
    )
    with pytest.raises(runner.CertificationError, match="branch"):
        runner.verify_source(args)


_SOURCE_HEAD = "1" * 40
_SOURCE_TREE = "2" * 40
_BASE_SHA = "3" * 40
_FEATURE_SHA = "4" * 40


def _source_args(
    root: Path,
    *,
    feature_ref: str | None = None,
    feature_head: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        root=root,
        expected_head=_SOURCE_HEAD,
        expected_tree=_SOURCE_TREE,
        expected_base_head=_BASE_SHA,
        expected_branch="feature/certification",
        expected_feature_ref=feature_ref,
        expected_feature_head=feature_head,
    )


def _install_source_git_state(
    monkeypatch: pytest.MonkeyPatch, root: Path, args: argparse.Namespace
) -> None:
    state = {
        ("branch", "--show-current"): args.expected_branch,
        ("rev-parse", "HEAD"): args.expected_head,
        ("show", "-s", "--format=%T", "HEAD"): args.expected_tree,
        ("rev-parse", "origin/develop"): args.expected_base_head,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
    }
    if args.expected_feature_ref:
        state[("rev-parse", args.expected_feature_ref)] = args.expected_feature_head

    def fake_git(actual_root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(root)
        return state[arguments]

    monkeypatch.setattr(runner, "_git", fake_git)


def _install_live_git(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, tuple[int, str, str]],
) -> list[str]:
    queried_refs: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        if command[1] == "check-ref-format":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        assert command[:4] == ["git", "ls-remote", "--exit-code", "origin"]
        assert len(command) == 5
        remote_ref = command[4]
        queried_refs.append(remote_ref)
        return_code, stdout, stderr = responses.get(remote_ref, (2, "", ""))
        return SimpleNamespace(returncode=return_code, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return queried_refs


def _ls_remote_line(sha: str, remote_ref: str) -> str:
    return f"{sha}\t{remote_ref}\n"


def test_live_develop_matching_expected_head_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _source_args(tmp_path)
    _install_source_git_state(monkeypatch, tmp_path, args)
    queried = _install_live_git(
        monkeypatch,
        {
            "refs/heads/develop": (
                0,
                _ls_remote_line(_BASE_SHA, "refs/heads/develop"),
                "",
            )
        },
    )

    identity = runner.verify_source(args)

    assert identity["base_head"] == _BASE_SHA
    assert identity["live_base_head"] == _BASE_SHA
    assert queried == ["refs/heads/develop"]


def test_live_develop_move_is_rejected_when_local_tracking_ref_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _source_args(tmp_path)
    _install_source_git_state(monkeypatch, tmp_path, args)
    moved = "5" * 40
    _install_live_git(
        monkeypatch,
        {"refs/heads/develop": (0, _ls_remote_line(moved, "refs/heads/develop"), "")},
    )

    with pytest.raises(runner.CertificationError, match="live_base_head"):
        runner.verify_source(args)


def test_live_feature_move_is_rejected_when_local_tracking_ref_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_ref = "origin/feature/certification"
    args = _source_args(tmp_path, feature_ref=feature_ref, feature_head=_FEATURE_SHA)
    _install_source_git_state(monkeypatch, tmp_path, args)
    moved = "6" * 40
    _install_live_git(
        monkeypatch,
        {
            "refs/heads/develop": (
                0,
                _ls_remote_line(_BASE_SHA, "refs/heads/develop"),
                "",
            ),
            "refs/heads/feature/certification": (
                0,
                _ls_remote_line(moved, "refs/heads/feature/certification"),
                "",
            ),
        },
    )

    with pytest.raises(runner.CertificationError, match="live_feature_head"):
        runner.verify_source(args)


def test_live_feature_query_maps_tracking_ref_to_exact_remote_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_ref = "refs/heads/feature/certification/performance"
    sha = "7" * 40
    queried = _install_live_git(
        monkeypatch, {feature_ref: (0, _ls_remote_line(sha, feature_ref), "")}
    )

    assert (
        runner._resolve_live_origin_branch_sha(
            tmp_path, "origin/feature/certification/performance"
        )
        == sha
    )
    assert queried == [feature_ref]


def test_live_origin_resolver_rejects_nontracking_ref_form(tmp_path: Path) -> None:
    with pytest.raises(runner.CertificationError, match="origin tracking ref"):
        runner._resolve_live_origin_branch_sha(
            tmp_path, "refs/remotes/origin/feature/certification"
        )


def test_missing_live_feature_ref_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queried = _install_live_git(monkeypatch, {})

    with pytest.raises(runner.CertificationError, match="missing"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/feature/certification")
    assert queried == ["refs/heads/feature/certification"]


@pytest.mark.parametrize(
    "stdout",
    [
        "not-a-sha\trefs/heads/develop\n",
        _ls_remote_line(_BASE_SHA, "refs/heads/develop")
        + _ls_remote_line(_FEATURE_SHA, "refs/heads/develop"),
    ],
)
def test_malformed_or_multiple_live_origin_response_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    _install_live_git(monkeypatch, {"refs/heads/develop": (0, stdout, "")})

    with pytest.raises(runner.CertificationError, match="Malformed live origin"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/develop")


def test_live_origin_query_failure_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_live_git(
        monkeypatch,
        {"refs/heads/develop": (128, "", "Could not resolve host")},
    )

    with pytest.raises(runner.CertificationError, match="ls-remote failed"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/develop")


def test_final_source_verification_repeats_live_origin_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inventory(tmp_path)
    monkeypatch.setattr(runner, "SERIAL_MODULES", ("tests/safety/test_serial.py",))
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path / "temp")
    args = _source_args(
        tmp_path,
        feature_ref="origin/feature/certification",
        feature_head=_FEATURE_SHA,
    )
    _install_source_git_state(monkeypatch, tmp_path, args)
    live_proofs: list[str] = []

    def resolve_live(root: Path, tracking_ref: str) -> str:
        live_proofs.append(tracking_ref)
        return _BASE_SHA if tracking_ref == "origin/develop" else _FEATURE_SHA

    monkeypatch.setattr(runner, "_resolve_live_origin_branch_sha", resolve_live)
    monkeypatch.setattr(
        runner,
        "run_children",
        lambda *args: {
            name: {"exit_code": 0} for name in ("broad-1", "broad-2", "serial")
        },
    )
    monkeypatch.setattr(
        runner,
        "run_static_checks",
        lambda *args: {
            name: {"exit_code": 0}
            for name in ("ruff_check", "ruff_format", "git_diff_check")
        },
    )
    args.python = Path("python")
    args.expected_feature_ref = "origin/feature/certification"
    args.temp_root = tmp_path / "temp"
    args.timeout_seconds = 1
    args.evidence_dir = tmp_path.parent / f"{tmp_path.name}-final-proof"
    args.plan = False

    summary = runner.run(args)

    assert summary["status"] == "passed"
    assert (
        live_proofs
        == [
            "origin/develop",
            "origin/feature/certification",
        ]
        * 3
    )
    assert summary["final_source"]["live_base_head"] == _BASE_SHA
    assert summary["final_source"]["live_feature_head"] == _FEATURE_SHA


def test_failed_child_sets_failed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inventory(tmp_path)
    monkeypatch.setattr(runner, "SERIAL_MODULES", ("tests/safety/test_serial.py",))
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
            "serial": {"exit_code": 0},
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


def test_feature_ref_must_name_origin(tmp_path: Path) -> None:
    args = argparse.Namespace(
        expected_feature_ref="HEAD",
        expected_feature_head="abc",
        timeout_seconds=1,
    )
    with pytest.raises(runner.CertificationError, match="origin tracking ref"):
        runner.run(args)
