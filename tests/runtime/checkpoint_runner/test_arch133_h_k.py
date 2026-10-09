from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _G133_NAME,
    _H133_NAME,
    _I133_NAME,
    _J133_NAME,
    _K133_NAME,
    _133h_copy,
    _133i_copy,
    _133j_copy,
    _133k_copy,
)


def test_133h_checkpoint_is_source_only_and_ci_registered():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_H133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133h"
    assert spec.tests == (
        *runner.ARCH133_H_K_TESTS,
        "tests/review_paper/test_unattended_publication.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS[-17:-15] == (_G133_NAME, _H133_NAME)
    assert runner._arch133_host_publication_authority_check(repo) == ()


@pytest.mark.parametrize("source", tuple(runner.ARCH133_PUBLICATION_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133h_complete_authority_pins_fail_closed(tmp_path, source, mutation):
    root = _133h_copy(tmp_path)
    path = root / source
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text() + "\nUNREVIEWED_EFFECT = True\n", encoding="utf-8"
        )
    assert runner._arch133_host_publication_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133h_runtime_capability_drift_rejected(tmp_path, monkeypatch, change):

    root = _133h_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_H133_NAME] = replace(specs[_H133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_publication_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133h_batch_workflow_registration_drift(tmp_path, target, mutation):
    root = _133h_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    line = (
        f'    "{_H133_NAME}",\n'
        if target == "runner"
        else f"              {_H133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_G133_NAME}",\n'
            if target == "runner"
            else f"              {_G133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_publication_authority_check(root)


def test_133h_verify_preflight_execute_callbacks_unreachable(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_H133_NAME]
    monkeypatch.setattr(
        runner, "_git_state", lambda *args: pytest.fail("host accessed")
    )
    with pytest.raises(RuntimeError, match="no read-only preflight"):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


def test_133i_source_only_registration_and_inert_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_I133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133i"
    assert spec.authority_check is runner._arch133_scratch_root_acl_authority_check
    assert runner.ACTIVE_CI_CHECKPOINTS[-16:-14] == (_H133_NAME, _I133_NAME)
    assert (
        runner._arch133_scratch_root_acl_authority_check(
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


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_SCRATCH_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133i_source_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133i_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133i_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133i_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_I133_NAME] = replace(specs[_I133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133i_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133i_copy(tmp_path, monkeypatch, workflow=True)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_I133_NAME}",\n'
        if target == "runner"
        else f"              {_I133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_H133_NAME}",\n'
            if target == "runner"
            else f"              {_H133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize(
    "old,new",
    [
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AI\temp\arch133i-root-acl-qualification-v1"',
        ),
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133"',
        ),
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133\qualification"',
        ),
        (
            r'PARENTS = ("F:\\", r"F:\AITradingBot")',
            r'PARENTS = ("F:\\", r"F:\AI", r"F:\AI\temp")',
        ),
    ],
)
def test_133i_relocated_namespace_pin_rejects_drift(tmp_path, monkeypatch, old, new):
    root = _133i_copy(tmp_path, monkeypatch)
    path = root / "src/trading_bot/arch133_acl/qualification.py"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8")
    assert runner._arch133_scratch_root_acl_authority_check(root)


def test_133j_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_J133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133j"
    assert spec.authority_check is runner._arch133_retained_root_authority_check
    assert runner.ACTIVE_CI_CHECKPOINTS[-15:-13] == (_I133_NAME, _J133_NAME)
    assert (
        runner._arch133_retained_root_authority_check(
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


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_RETAINED_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133j_read_only_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133j_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_retained_root_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133j_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133j_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_J133_NAME] = replace(specs[_J133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_retained_root_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133j_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133j_copy(tmp_path, monkeypatch, workflow=True)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_J133_NAME}",\n'
        if target == "runner"
        else f"              {_J133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_I133_NAME}",\n'
            if target == "runner"
            else f"              {_I133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_retained_root_authority_check(root)


def test_133k_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_K133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133k"
    assert spec.authority_check is runner._arch133_recovery_authority_check
    assert runner.ACTIVE_CI_CHECKPOINTS[-14:-12] == (_J133_NAME, _K133_NAME)
    assert (
        runner._arch133_recovery_authority_check(
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


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_RECOVERY_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133k_read_only_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133k_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_recovery_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133k_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133k_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_K133_NAME] = replace(specs[_K133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_recovery_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133k_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133k_copy(tmp_path, monkeypatch, workflow=True)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_K133_NAME}",\n'
        if target == "runner"
        else f"              {_K133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_J133_NAME}",\n'
            if target == "runner"
            else f"              {_J133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_recovery_authority_check(root)


@pytest.mark.parametrize(
    "authority,predecessor",
    [
        (
            "_arch133_scratch_root_acl_authority_check",
            "_arch133_host_publication_authority_check",
        ),
        (
            "_arch133_retained_root_authority_check",
            "_arch133_scratch_root_acl_authority_check",
        ),
        ("_arch133_recovery_authority_check", "_arch133_retained_root_authority_check"),
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


def test_copied_133h_authority_baseline_passes(tmp_path):
    assert runner._arch133_host_publication_authority_check(_133h_copy(tmp_path)) == ()


@pytest.mark.parametrize("workflow", [False, True], ids=["local", "workflow"])
@pytest.mark.parametrize(
    "copy,authority",
    [
        (_133i_copy, runner._arch133_scratch_root_acl_authority_check),
        (_133j_copy, runner._arch133_retained_root_authority_check),
        (_133k_copy, runner._arch133_recovery_authority_check),
    ],
)
def test_copied_local_authority_baseline_passes(
    tmp_path, monkeypatch, copy, authority, workflow
):
    assert authority(copy(tmp_path, monkeypatch, workflow=workflow)) == ()
