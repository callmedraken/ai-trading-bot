from dataclasses import replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest
from scripts.arch147_p6_tiny_live_source import authority_failures

from scripts import arch147_p6_tiny_live_source as source
from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current

ROOT = Path(runner.__file__).resolve().parents[1]


def test_p6_is_registered_with_bounded_live_dispatch():
    spec = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    assert spec.remote_branch == runner.ARCH147_P6_BRANCH
    assert spec.preflight is runner._arch147_p6_preflight
    assert spec.execute is runner._arch147_p6_execute
    route = runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert route.count(spec.name) == 1
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == spec.name
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert authority_failures(ROOT) == ()
    assert current.current_preflight_dispatch_failures(ROOT) == ()


def test_p6_preflight_and_execute_are_not_p5b_facade_methods():
    p5b = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    p6 = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    assert p5b.execute is None
    assert p6.execute is runner._arch147_p6_execute
    assert p6.preflight is not p5b.preflight


def _arch147_p6_preflight():
    return {}


def _clone_p6_callbacks():
    return tuple(
        FunctionType(
            callback.__code__,
            callback.__globals__,
            callback.__name__,
        )
        for callback in (
            runner._arch147_p6_authority_check,
            runner._arch147_p6_preflight,
            runner._arch147_p6_execute,
        )
    )


def test_p6_registration_matches_cloned_callbacks_but_rejects_drift():
    canonical = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    cloned_authority, cloned_preflight, cloned_execute = _clone_p6_callbacks()
    foreign = replace(
        canonical,
        authority_check=cloned_authority,
        preflight=cloned_preflight,
        execute=cloned_execute,
    )

    assert foreign != canonical
    assert source._same_p6_registration(foreign, canonical, ROOT)

    changed = {
        "name": "other",
        "description": "other",
        "tests": canonical.tests + ("tests/other.py",),
        "ruff_paths": canonical.ruff_paths + ("other.py",),
        "remote_branch": "other",
        "remote_head_env": "OTHER_HEAD",
    }
    for field, value in changed.items():
        assert not source._same_p6_registration(
            replace(foreign, **{field: value}), canonical, ROOT
        )

    wrong_name = FunctionType(
        runner._arch147_p6_preflight.__code__,
        runner._arch147_p6_preflight.__globals__,
        "wrong_name",
    )
    assert not source._same_p6_registration(
        replace(foreign, preflight=wrong_name), canonical, ROOT
    )
    assert not source._same_p6_registration(
        replace(foreign, preflight=_arch147_p6_preflight), canonical, ROOT
    )


def _fake_p6_admission(monkeypatch):
    canonical = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    _, cloned_preflight, _ = _clone_p6_callbacks()
    spec = replace(canonical, preflight=cloned_preflight)
    calls = []
    monkeypatch.setattr(
        "trading_bot.desktop_live.preflight.preflight",
        lambda: calls.append("preflight") or {"status": "PASS"},
    )
    monkeypatch.setattr(source, "authority_failures", lambda root: ())
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": runner.ARCH147_P6_BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda root, branch: state["head"],
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
    "mismatch", ["dirty", "feature", "develop", "branch", "authority", "prospective"]
)
def test_p6_preflight_integration_admission_blocks_before_attempt(
    monkeypatch, tmp_path, mismatch
):
    spec, state, calls = _fake_p6_admission(monkeypatch)
    if mismatch == "dirty":
        state["porcelain"] = "M file"
    elif mismatch == "branch":
        state["branch"] = "other"
    elif mismatch == "authority":
        monkeypatch.setattr(source, "authority_failures", lambda root: ("rejected",))
    elif mismatch == "prospective":
        monkeypatch.setattr(
            current,
            "evaluate_source_authority",
            lambda **kwargs: SimpleNamespace(passed=False),
        )
    else:
        remote_head = "c" * 40
        remote_branch = runner.ARCH147_P6_BRANCH if mismatch == "feature" else "develop"
        monkeypatch.setattr(
            runner,
            "_remote_branch_head",
            lambda root, branch: (
                remote_head if branch == remote_branch else state["head"]
            ),
        )

    with pytest.raises(RuntimeError):
        source.run_preflight(spec, repo_root=ROOT, evidence_root=tmp_path)

    assert calls == []
    assert not list(tmp_path.iterdir())


def test_p6_preflight_integration_admission_creates_one_consumed_attempt(
    monkeypatch, tmp_path
):
    spec, state, calls = _fake_p6_admission(monkeypatch)
    monkeypatch.setattr(runner, "_stamp", lambda: "fixed-attempt")

    passed, report = runner.preflight_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path
    )

    assert passed
    assert calls == ["preflight"]
    assert report is not None and report.is_file()
    body = report.read_text(encoding="utf-8")
    assert state["head"] in body


@pytest.mark.parametrize("mismatch", ["develop", "prospective"])
def test_p6_execute_integration_admission_blocks_before_attempt(
    monkeypatch, tmp_path, mismatch
):
    spec = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": runner.ARCH147_P6_BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: dict(state))
    monkeypatch.setattr(
        runner,
        "_git_output",
        lambda *args: "https://github.com/callmedraken/ai-trading-bot.git",
    )
    monkeypatch.setattr(source, "authority_failures", lambda root: ())
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda root, branch: (
            "c" * 40 if mismatch == "develop" and branch == "develop" else state["head"]
        ),
    )
    monkeypatch.setattr(
        current,
        "evaluate_source_authority",
        lambda **kwargs: SimpleNamespace(passed=mismatch != "prospective"),
    )

    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(spec, repo_root=ROOT, evidence_root=tmp_path)

    assert not list(tmp_path.iterdir())


def test_p6_execute_admits_exact_source_before_delegation(monkeypatch, tmp_path):
    spec = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    state = {"head": "a" * 40, "tree": "b" * 40, "porcelain": ""}
    calls = []
    monkeypatch.setattr(runner, "_git_state", lambda root: dict(state))

    def admit(actual, *, repo_root, evidence_root, state):
        assert actual is spec
        assert repo_root == ROOT
        assert evidence_root == tmp_path
        assert state == {"head": "a" * 40, "tree": "b" * 40, "porcelain": ""}
        calls.append("admission")

    def delegate(actual, *, repo_root, evidence_root):
        assert actual is spec
        assert (repo_root, evidence_root) == (ROOT, tmp_path)
        assert calls == ["admission"]
        calls.append("delegation")
        return False, tmp_path / "synthetic-report.json"

    monkeypatch.setattr(source, "require_protected_execution_source", admit)
    monkeypatch.setattr(runner, "_PRE_ARCH147_P6_EXECUTE_CHECKPOINT", delegate)
    assert runner.execute_checkpoint(spec, repo_root=ROOT, evidence_root=tmp_path) == (
        False,
        tmp_path / "synthetic-report.json",
    )
    assert calls == ["admission", "delegation"]
    assert not list(tmp_path.iterdir())


def test_non_p6_execution_preserves_predecessor_delegation(monkeypatch, tmp_path):
    spec = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    calls = []

    def forbidden(*args, **kwargs):
        pytest.fail("non-P6 checkpoint entered P6 source admission")

    def delegate(actual, *, repo_root, evidence_root):
        calls.append((actual, repo_root, evidence_root))
        return False, tmp_path / "synthetic-report.json"

    monkeypatch.setattr(source, "require_protected_execution_source", forbidden)
    monkeypatch.setattr(runner, "_git_state", forbidden)
    monkeypatch.setattr(runner, "_PRE_ARCH147_P6_EXECUTE_CHECKPOINT", delegate)
    runner.execute_checkpoint(spec, repo_root=ROOT, evidence_root=tmp_path)
    assert calls == [(spec, ROOT, tmp_path)]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "mismatch",
    [
        "dirty",
        "feature",
        "develop",
        "branch",
        "authority",
        "prospective",
        "origin",
        "unstable",
    ],
)
def test_kill_reuses_integrated_admission_without_provider_or_attempt(
    monkeypatch, tmp_path, mismatch
):
    _, state, calls = _fake_p6_admission(monkeypatch)
    if mismatch == "dirty":
        state["porcelain"] = "M file"
    elif mismatch == "branch":
        state["branch"] = "other"
    elif mismatch == "authority":
        monkeypatch.setattr(source, "authority_failures", lambda root: ("rejected",))
    elif mismatch == "prospective":
        monkeypatch.setattr(
            current,
            "evaluate_source_authority",
            lambda **kwargs: SimpleNamespace(passed=False),
        )
    elif mismatch == "origin":
        monkeypatch.setattr(runner, "_git_output", lambda *args: "other-origin")
    elif mismatch == "unstable":
        states = iter([state, {**state, "tree": "f" * 40}])
        monkeypatch.setattr(runner, "_git_state", lambda root: next(states))
    else:
        branch = runner.ARCH147_P6_BRANCH if mismatch == "feature" else "develop"
        monkeypatch.setattr(
            runner,
            "_remote_branch_head",
            lambda root, name: "e" * 40 if name == branch else state["head"],
        )
    with pytest.raises(RuntimeError):
        source.require_kill_source(ROOT, tmp_path / "new-evidence")
    assert calls == []
    assert not list(tmp_path.iterdir())


def test_kill_integrated_admission_is_read_only_and_returns_exact_identity(
    monkeypatch, tmp_path
):
    _, state, calls = _fake_p6_admission(monkeypatch)
    assert source.require_kill_source(ROOT, tmp_path / "new-evidence") == (
        state["head"],
        state["tree"],
    )
    assert calls == []
    assert not list(tmp_path.iterdir())


def test_p6_source_inventory_owns_kill_and_binding():
    assert {
        "src/trading_bot/desktop_live/ownership.py",
        "src/trading_bot/desktop_live/kill_operator.py",
    } <= set(source.P6_MODULES)


@pytest.mark.parametrize(
    "capability",
    [
        "place_equity_order",
        "review_equity_order",
        "place_option_order",
        "place_crypto_order",
        "call_tool",
        "LIVE_ARM_ENV",
    ],
)
def test_kill_source_checker_rejects_unreviewed_authority(capability):
    import ast

    assert source.kill_surface_failures(ast.parse("transport." + capability))
    assert source.kill_surface_failures(ast.parse("from anything import " + capability))
    assert (
        source.kill_surface_failures(ast.parse("transport.get_equity_orders({})")) == ()
    )
