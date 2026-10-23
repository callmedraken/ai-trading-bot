from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner


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


@pytest.mark.parametrize(
    "outcome", ["pass", "nonzero", "timeout", "missing", "malformed", "cases"]
)
def test_six_children_start_before_wait_and_retain_exact_evidence(
    tmp_path, monkeypatch, outcome
):
    started = []
    killed = []
    lanes = {f"broad-{i}": (f"tests/domain/test_module_{i}.py",) for i in range(1, 7)}

    class Process:
        returncode = 0

        def __init__(self, index):
            self.index = index

        def wait(self, timeout=None):
            assert len(started) == 6
            if self.index == 2 and outcome == "timeout" and timeout is not None:
                raise runner.subprocess.TimeoutExpired("pytest", timeout)
            self.returncode = 7 if self.index == 2 and outcome == "nonzero" else 0
            return self.returncode

        def kill(self):
            killed.append(self.index)

    def popen(command, **kwargs):
        index = len(started) + 1
        started.append(command)
        assert kwargs["cwd"] == tmp_path
        assert command[:3] == ["python", "-m", "pytest"]
        assert command[3:4] == list(lanes[f"broad-{index}"])
        path = Path(command[command.index("--junitxml") + 1])
        if index == 2 and outcome == "missing":
            pass
        elif index == 2 and outcome == "malformed":
            path.write_text("<testsuite>", encoding="utf-8")
        else:
            extra = (
                (
                    "<testcase name='failed'><failure/></testcase>"
                    "<testcase name='errored'><error/></testcase>"
                )
                if (index == 2 and outcome == "cases")
                else ""
            )
            path.write_text(
                "<testsuite><testcase name='ok'/>"
                "<testcase name='skip'><skipped/></testcase>" + extra + "</testsuite>",
                encoding="utf-8",
            )
        return Process(index)

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    args = SimpleNamespace(
        root=tmp_path, python=Path("python"), temp_root=tmp_path, timeout_seconds=1
    )
    results = runner.run_children(args, lanes, tmp_path)
    assert tuple(results) == tuple(lanes)
    assert len({child["basetemp"] for child in results.values()}) == 6
    for name, child in results.items():
        if name == "broad-2" and outcome != "pass":
            assert "error" in child
            if outcome == "timeout":
                assert "timed out" in child["error"]
            if outcome == "nonzero":
                assert child["exit_code"] == 7
        else:
            assert "error" not in child
            assert child["counts"] == dict(
                cases=2, passed=1, skipped=1, failed=0, errors=0
            )
    assert killed == ([2] if outcome == "timeout" else [])
    if outcome == "cases":
        assert results["broad-2"]["counts"] == dict(
            cases=4, passed=1, skipped=1, failed=1, errors=1
        )
