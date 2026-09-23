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
