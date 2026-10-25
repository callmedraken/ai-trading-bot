from pathlib import Path

import pytest
from tests.runtime.checkpoint_runner.test_ci import _reuse_fixture

from scripts import checkpoint_runner as runner


def test_r3m_coherent_attempt_two_is_not_reusable():
    args, responses, run, jobs, _, jobs_path = _reuse_fixture()
    prefix = "repos/callmedraken/ai-trading-bot"
    run["run_attempt"] = 2
    responses[f"{prefix}/actions/runs/100"]["run_attempt"] = 2
    for job in jobs:
        job["run_attempt"] = 2
    attempt_two_jobs_path = f"{prefix}/actions/runs/100/attempts/2/jobs?per_page=100"
    responses[attempt_two_jobs_path] = responses.pop(jobs_path)

    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)

    assert result["reuse"] is False


def test_r3m_c2_preserves_predecessors_and_authorizes_overlay(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch132_r3m_c2_authority_check(root) == ()
    assert runner._arch132_r3m_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH132_R3M_C2_AST_PREDECESSORS, runner.ARCH132_R3M_C2_AST_PINS),
        (
            False,
            runner.ARCH132_R3M_C2_BLOB_PREDECESSORS,
            runner.ARCH132_R3M_C2_BLOB_PINS,
        ),
    ):
        for key, pin in before.items():
            assert runner._arch132_r3m_c2_pin(key, pin, ast_pin=ast_pin) == after[key]
            with pytest.raises(ValueError, match="R3M C2 wrong exact predecessor"):
                runner._arch132_r3m_c2_pin(key, "0" * len(pin), ast_pin=ast_pin)
    monkeypatch.setattr(runner, "ARCH132_R3M_C2_AST_PINS", {})
    assert runner._arch132_r3m_c2_authority_check(root)
