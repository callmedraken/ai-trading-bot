"""P5B source authority never dispatches the registered protected reader."""

import json
from dataclasses import replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest

from scripts import arch147_p5b_source as source
from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current
from scripts import run_test_certification as certification
from trading_bot.desktop_paper import robinhood_preflight

ROOT = Path(runner.__file__).resolve().parents[1]


def _arch147_p5b_preflight():
    return {}


def _clone_p5b_callbacks():
    return (
        FunctionType(
            runner._arch147_p5b_authority_check.__code__,
            runner._arch147_p5b_authority_check.__globals__,
            runner._arch147_p5b_authority_check.__name__,
        ),
        FunctionType(
            runner._arch147_p5b_preflight.__code__,
            runner._arch147_p5b_preflight.__globals__,
            runner._arch147_p5b_preflight.__name__,
        ),
    )


def test_p5b_registration_matches_cloned_callbacks_but_rejects_drift():
    canonical = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    cloned_authority, cloned_preflight = _clone_p5b_callbacks()
    foreign = replace(
        canonical,
        authority_check=cloned_authority,
        preflight=cloned_preflight,
    )

    assert foreign != canonical
    assert source._same_p5b_registration(foreign, canonical, ROOT)

    changed = {
        "name": "other",
        "description": "other",
        "tests": canonical.tests + ("tests/other.py",),
        "ruff_paths": canonical.ruff_paths + ("other.py",),
        "remote_branch": "other",
        "remote_head_env": "OTHER_HEAD",
        "execute": lambda: None,
    }
    for field, value in changed.items():
        assert not source._same_p5b_registration(
            replace(foreign, **{field: value}), canonical, ROOT
        )

    wrong_name = FunctionType(
        runner._arch147_p5b_preflight.__code__,
        runner._arch147_p5b_preflight.__globals__,
        "wrong_name",
    )
    assert not source._same_p5b_registration(
        replace(foreign, preflight=wrong_name), canonical, ROOT
    )
    assert not source._same_p5b_registration(
        replace(foreign, preflight=_arch147_p5b_preflight), canonical, ROOT
    )


def test_read_preflight_only_full_mapping_current_and_historical_authority():
    spec = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    assert spec.remote_branch == runner.ARCH147_P5B_BRANCH
    assert spec.preflight is runner._arch147_p5b_preflight
    assert spec.execute is spec.remote_head_env is None
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[1] == spec.name
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert source.authority_failures(ROOT) == ()
    assert current.current_preflight_dispatch_failures(ROOT) == ()
    assert current.historical_preflight_dispatch_failures(ROOT) == ()
    full = set(
        certification.select_inventory(certification.discover_inventory(ROOT), "full")
    )
    assert (set(spec.tests) - set(runner.ARCH147_P5A_TESTS)) <= full


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_workflow_projection_rejects_changed_p5b_route(mutation):
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    row = f"              {runner.ARCH147_P5B_NAME} `\n"
    following = f"              {runner.ARCH147_FILTERED_TREND_NAME} `\n"
    changed = {
        "missing": workflow.replace(row, "", 1),
        "duplicate": workflow.replace(row, row + row, 1),
        "reordered": workflow.replace(row + following, following + row, 1),
    }[mutation]
    assert runner._arch147_current_batch_workflow_is_reviewed(workflow)
    assert not runner._arch147_current_batch_workflow_is_reviewed(changed)


def fake_admission(monkeypatch):
    calls = []
    canonical = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    _, cloned_preflight = _clone_p5b_callbacks()
    spec = replace(
        canonical,
        preflight=cloned_preflight,
    )
    monkeypatch.setattr(
        robinhood_preflight,
        "preflight",
        lambda: calls.append("read") or {"status": "PASS", "mutation_call_count": 0},
    )
    monkeypatch.setattr(source, "authority_failures", lambda root: ())
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": runner.ARCH147_P5B_BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: dict(state))
    monkeypatch.setattr(
        runner, "_remote_branch_head", lambda root, branch: state["head"]
    )
    monkeypatch.setattr(
        runner,
        "_git_output",
        lambda *args: "https://github.com/callmedraken/ai-trading-bot.git",
    )
    monkeypatch.setattr(
        current,
        "evaluate_source_authority",
        lambda **kwargs: SimpleNamespace(passed=True),
    )
    return spec, state, calls


@pytest.mark.parametrize(
    "mismatch", ["dirty", "develop", "branch", "authority", "evidence"]
)
def test_source_gate_stops_before_provider_for_unaccepted_state(
    monkeypatch, tmp_path, mismatch
):
    spec, state, calls = fake_admission(monkeypatch)
    evidence = tmp_path
    if mismatch == "dirty":
        state["porcelain"] = "M file"
    elif mismatch == "develop":
        monkeypatch.setattr(
            runner,
            "_remote_branch_head",
            lambda root, branch: "c" * 40 if branch == "develop" else state["head"],
        )
    elif mismatch == "branch":
        state["branch"] = "other"
    elif mismatch == "authority":
        monkeypatch.setattr(source, "authority_failures", lambda root: ("rejected",))
    else:
        evidence = ROOT / "evidence"
    with pytest.raises(RuntimeError):
        source.run_preflight(spec, repo_root=ROOT, evidence_root=evidence)
    assert calls == []
    assert not list(tmp_path.iterdir())


def test_registered_dispatch_creates_sanitized_exact_source_evidence_once(
    monkeypatch, tmp_path
):
    spec, state, calls = fake_admission(monkeypatch)
    real_resolve = type(ROOT).resolve
    reviewed_root = source.Path(r"F:\AI\worktrees") / "arch147-p5b-test-fixture"

    def fixture_resolve(self, *args, **kwargs):
        if self == ROOT:
            return reviewed_root
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(type(ROOT), "resolve", fixture_resolve)
    assert reviewed_root.parent == source.Path(r"F:\AI\worktrees")
    monkeypatch.setattr(runner, "_stamp", lambda: "fixed-attempt")
    passed, path = runner.preflight_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path
    )
    assert passed and calls == ["read"]
    report = json.loads(path.read_text())
    assert report["source_head"] == state["head"]
    assert report["source_tree"] == state["tree"]
    assert report["result"]["mutation_call_count"] == 0
    assert (path.parent / "attempt.json").is_file()
    with pytest.raises(FileExistsError):
        runner.preflight_checkpoint(spec, repo_root=ROOT, evidence_root=tmp_path)
    assert calls == ["read"]


def test_non_p5b_dispatch_delegates_to_unchanged_historical_outer(
    monkeypatch, tmp_path
):
    spec = runner._checkpoint_specs()[runner.ARCH146_PARTIAL_STATE_NAME]
    calls = []
    monkeypatch.setattr(
        runner,
        "_arch146_partial_state_preflight_checkpoint",
        lambda *args, **kwargs: calls.append(args[0]) or (False, None),
    )
    assert runner.preflight_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path
    ) == (False, None)
    assert calls == [spec]
