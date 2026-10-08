from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _K133_NAME,
    _L133_NAME,
    _M133_NAME,
    _133l_copy,
    _133m_copy,
    _copy_chain_authority,
    _copy_local_authority,
)


def test_133l_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_L133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133l"
    assert runner.ACTIVE_CI_CHECKPOINTS[-4:-1] == (_K133_NAME, _L133_NAME, _M133_NAME)
    assert (
        runner._arch133_verifier_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_VERIFIER_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133l_complete_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133l_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_verifier_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("host accessed")},
        {"execute": lambda: pytest.fail("host accessed")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133l_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133l_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_L133_NAME] = replace(specs[_L133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_verifier_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133l_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133l_copy(tmp_path, monkeypatch, isolate_predecessor=False)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_L133_NAME}",\n'
        if target == "runner"
        else f"              {_L133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_K133_NAME}",\n'
            if target == "runner"
            else f"              {_K133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_verifier_authority_check(root)


def test_133m_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_M133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133m"
    assert runner.ACTIVE_CI_CHECKPOINTS[-3:-1] == (_L133_NAME, _M133_NAME)
    assert (
        runner._arch133_diagnostic_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_DIAGNOSTIC_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133m_complete_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133m_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_diagnostic_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("host accessed")},
        {"execute": lambda: pytest.fail("host accessed")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133m_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133m_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_M133_NAME] = replace(specs[_M133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_diagnostic_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133m_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133m_copy(tmp_path, monkeypatch, isolate_predecessor=False)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_M133_NAME}",\n'
        if target == "runner"
        else f"              {_M133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_L133_NAME}",\n'
            if target == "runner"
            else f"              {_L133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_diagnostic_authority_check(root)


@pytest.mark.parametrize(
    "authority,predecessor",
    [
        ("_arch133_verifier_authority_check", "_arch133_recovery_authority_check"),
        ("_arch133_diagnostic_authority_check", "_arch133_verifier_authority_check"),
        (
            "_arch133_publication_diagnostic_authority_check",
            "_arch133_diagnostic_authority_check",
        ),
    ],
)
@pytest.mark.parametrize("failure", [(), ("predecessor rejected",)])
def test_predecessor_called_once_and_failure_propagates(
    monkeypatch, authority, predecessor, failure
):
    repo = Path(runner.__file__).resolve().parents[1]
    seen = []

    def previous(root):
        seen.append(root)
        return failure

    monkeypatch.setattr(runner, predecessor, previous)
    assert getattr(runner, authority)(repo) == failure
    assert seen == [repo]


def test_full_real_authority_chain_passes_and_visits_every_predecessor(monkeypatch):
    repo = Path(runner.__file__).resolve().parents[1]
    seen = []
    names = (
        "_arch133_verifier_authority_check",
        "_arch133_recovery_authority_check",
        "_arch133_retained_root_authority_check",
        "_arch133_scratch_root_acl_authority_check",
        "_arch133_host_publication_authority_check",
    )
    for name in names:
        original = getattr(runner, name)

        def traced(root, original=original, name=name):
            seen.append((name, root))
            return original(root)

        monkeypatch.setattr(runner, name, traced)
    # Capability identity checks refer to the real functions. Keep the registered
    # spec identities real while transparently tracing calls through the chain.
    registry = runner._checkpoint_specs()
    # The registry is built after wrapping, so identities match each wrapper.
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: registry)
    assert runner._arch133_diagnostic_authority_check(repo) == ()
    assert seen == [(name, repo) for name in names]


_N133_NAME = "arch133-robinhood-publication-state-paper-diagnostic"


def _133n_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_diagnostic_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(
            tmp_path, runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS
        )
    else:
        root = _copy_chain_authority(
            tmp_path, runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS
        )
    assert runner._arch133_publication_diagnostic_authority_check(root) == ()
    return root


def test_133n_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_N133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133n"
    assert runner.ACTIVE_CI_CHECKPOINTS[-3:] == (_L133_NAME, _M133_NAME, _N133_NAME)
    assert (
        runner._arch133_publication_diagnostic_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133n_complete_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133n_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_publication_diagnostic_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("host accessed")},
        {"execute": lambda: pytest.fail("host accessed")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133n_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133n_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_N133_NAME] = replace(specs[_N133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_publication_diagnostic_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133n_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133n_copy(tmp_path, monkeypatch, isolate_predecessor=False)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_N133_NAME}",\n'
        if target == "runner"
        else f"              {_N133_NAME}\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_M133_NAME}",\n'
            if target == "runner"
            else f"              {_M133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_publication_diagnostic_authority_check(root)
