from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _H133_NAME,
    _K133_NAME,
    _L133_NAME,
    _M133_NAME,
    _133l_copy,
    _133m_copy,
    _copy_chain_authority,
    _copy_mutation_authority,
)


def test_133l_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_L133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133l"
    assert runner.ACTIVE_CI_CHECKPOINTS[-14:-11] == (_K133_NAME, _L133_NAME, _M133_NAME)
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
    root = _133l_copy(tmp_path, monkeypatch, workflow=True)
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
    assert runner.ACTIVE_CI_CHECKPOINTS[-13:-11] == (_L133_NAME, _M133_NAME)
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
    root = _133m_copy(tmp_path, monkeypatch, workflow=True)
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
        (
            "_arch133_publication_corrected_authority_check",
            "_arch133_publication_diagnostic_authority_check",
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


def _133n_copy(tmp_path, monkeypatch, *, workflow=False):
    return _copy_mutation_authority(
        tmp_path,
        monkeypatch,
        "_arch133_diagnostic_authority_check",
        runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS,
        workflow=workflow,
    )


def test_133n_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_N133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133n"
    assert runner.ACTIVE_CI_CHECKPOINTS[-13:-10] == (_L133_NAME, _M133_NAME, _N133_NAME)
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
    root = _133n_copy(tmp_path, monkeypatch, workflow=True)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_N133_NAME}",\n'
        if target == "runner"
        else f"              {_N133_NAME} `\n"
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


_O133_NAME = "arch133-robinhood-publication-state-paper-corrected"


def _133o_copy(tmp_path, monkeypatch, *, workflow=False):
    return _copy_mutation_authority(
        tmp_path,
        monkeypatch,
        "_arch133_publication_diagnostic_authority_check",
        runner.ARCH133_PUBLICATION_CORRECTED_PINS,
        workflow=workflow,
    )


def test_133o_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_O133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133o"
    assert runner.ACTIVE_CI_CHECKPOINTS[-11:-9] == (_N133_NAME, _O133_NAME)
    assert (
        runner._arch133_publication_corrected_authority_check(
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


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_PUBLICATION_CORRECTED_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133o_complete_import_closure_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133o_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_publication_corrected_authority_check(root)


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
def test_133o_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):

    root = _133o_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_O133_NAME] = replace(specs[_O133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_publication_corrected_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133o_ci_registration_drift_fails_closed(
    tmp_path, monkeypatch, target, mutation
):
    root = _133o_copy(tmp_path, monkeypatch, workflow=True)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_O133_NAME}",\n'
        if target == "runner"
        else f"              {_O133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_N133_NAME}",\n'
            if target == "runner"
            else f"              {_N133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_publication_corrected_authority_check(root)


@pytest.mark.parametrize("workflow", [False, True], ids=["local", "workflow"])
@pytest.mark.parametrize(
    "copy,authority",
    [
        (_133l_copy, runner._arch133_verifier_authority_check),
        (_133m_copy, runner._arch133_diagnostic_authority_check),
        (_133n_copy, runner._arch133_publication_diagnostic_authority_check),
        (_133o_copy, runner._arch133_publication_corrected_authority_check),
    ],
)
def test_copied_local_authority_baseline_passes(
    tmp_path, monkeypatch, copy, authority, workflow
):
    assert authority(copy(tmp_path, monkeypatch, workflow=workflow)) == ()


@pytest.mark.parametrize(
    "mutation", ["accepted", "predecessor_pin", "runner", "workflow"]
)
def test_complete_133p_real_chain_pass_and_rejection(tmp_path, monkeypatch, mutation):
    root = _copy_chain_authority(tmp_path, runner.ARCH133_SCHEDULER_PINS)
    expected = None
    if mutation == "predecessor_pin":
        # This source belongs to H and is outside P's local pin closure.
        relative = "scripts/run_arch133_host_publication.py"
        assert relative not in runner.ARCH133_SCHEDULER_PINS
        (root / relative).unlink()
        expected = "133-H source or structural boundary unavailable"
    elif mutation in ("runner", "workflow"):
        path = root / (
            "scripts/checkpoint_runner.py"
            if mutation == "runner"
            else ".github/workflows/checkpoint-source-gates.yml"
        )
        line = (
            f'    "{_H133_NAME}",\n'
            if mutation == "runner"
            else f"              {_H133_NAME} `\n"
        )
        text = path.read_text(encoding="utf-8")
        assert text.count(line) == 1
        path.write_text(text.replace(line, ""), encoding="utf-8")
        expected = (
            "133-H batch registration drift"
            if mutation == "runner"
            else "133-H workflow invocation drift"
        )
    names = (
        "_arch133_publication_corrected_authority_check",
        "_arch133_publication_diagnostic_authority_check",
        "_arch133_diagnostic_authority_check",
        "_arch133_verifier_authority_check",
        "_arch133_recovery_authority_check",
        "_arch133_retained_root_authority_check",
        "_arch133_scratch_root_acl_authority_check",
        "_arch133_host_publication_authority_check",
    )
    seen = []
    for name in names:
        original = getattr(runner, name)

        def traced(repo, original=original, name=name):
            seen.append((name, repo))
            return original(repo)

        monkeypatch.setattr(runner, name, traced)
    registry = runner._checkpoint_specs()
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: registry)
    failures = runner._arch133_scheduler_installation_authority_check(root)
    assert seen == [(name, root) for name in names]
    if expected is None:
        assert failures == ()
    else:
        assert expected in failures


_S133_NAME = "arch133-robinhood-reprovision-parent-security-diagnostic"
_R133_NAME = "arch133-robinhood-reprovision-admission-diagnostic"


def _133s_copy(tmp_path, monkeypatch):
    # B4: copy only the local sources and bounded real contract AST. Each matrix
    # checks the immediate edge; one separate test runs the real complete chain.
    from .helpers import _authority_fixture_text

    repo = Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(
        runner, "_arch133_reprovision_diagnostic_authority_check", lambda _: ()
    )
    for relative in (
        *runner.ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_authority_fixture_text(repo, relative), encoding="utf-8")
    return tmp_path


def test_133s_real_chain_and_source_only_registration(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_S133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133s"
    assert runner.ACTIVE_CI_CHECKPOINTS[-7:-5] == (_R133_NAME, _S133_NAME)
    assert spec.tests == (
        *runner.ARCH133_L_M_TESTS,
        "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/review_paper/test_arch133_parent_security_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_L_M_RUFF_PATHS,
        *runner.ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES,
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/review_paper/test_arch133_parent_security_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parents[1]) == ()
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    for invoke in (runner.preflight_checkpoint, runner.execute_checkpoint):
        with pytest.raises(RuntimeError):
            invoke(spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence")


@pytest.mark.parametrize(
    "relative", tuple(runner.ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS)
)
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133s_complete_local_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133s_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_parent_security_diagnostic_authority_check(root)


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
def test_133s_registration_capability_injection_fails_closed(
    tmp_path, monkeypatch, change
):
    root = _133s_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_S133_NAME] = replace(specs[_S133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_parent_security_diagnostic_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133s_active_order_drift_fails_closed(tmp_path, monkeypatch, target, mutation):
    root = _133s_copy(tmp_path, monkeypatch)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    if target == "runner":
        line, prior = f'    "{_S133_NAME}",\n', f'    "{_R133_NAME}",\n'
    else:
        line, prior = (
            f"              {_S133_NAME} `\n",
            f"              {_R133_NAME} `\n",
        )
    assert text.count(line) == 1
    if mutation == "order":
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_parent_security_diagnostic_authority_check(root)


def test_133s_copied_baseline_passes_without_whole_chain_setup(tmp_path, monkeypatch):
    assert (
        runner._arch133_parent_security_diagnostic_authority_check(
            _133s_copy(tmp_path, monkeypatch)
        )
        == ()
    )


@pytest.mark.parametrize("failure", [(), ("predecessor rejected",)])
def test_133s_predecessor_called_once_and_failure_propagates(monkeypatch, failure):
    root = Path(runner.__file__).resolve().parents[1]
    seen = []

    def previous(repo):
        seen.append(repo)
        return failure

    monkeypatch.setattr(
        runner, "_arch133_reprovision_diagnostic_authority_check", previous
    )
    assert runner._arch133_parent_security_diagnostic_authority_check(root) == failure
    assert seen == [root]


@pytest.mark.parametrize("mutation", ["inventory", "registration"])
def test_133s_pin_inventory_and_source_registration_drift(
    tmp_path, monkeypatch, mutation
):
    root = _133s_copy(tmp_path, monkeypatch)
    if mutation == "inventory":
        monkeypatch.setattr(runner, "ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES", ())
    else:
        path = root / "scripts/checkpoint_runner.py"
        text = path.read_text(encoding="utf-8")
        # Mutate only the S capability in the copied source contract.
        start = text.index(f'"{_S133_NAME}": CheckpointSpec(')
        text = text[:start] + text[start:].replace(
            "preflight=None", "preflight=unreviewed", 1
        )
        path.write_text(text, encoding="utf-8")
    assert runner._arch133_parent_security_diagnostic_authority_check(root)


_T133_NAME = "arch133-robinhood-reprovision-parent-policy-diagnostic"
_S133_NAME = "arch133-robinhood-reprovision-parent-security-diagnostic"


def _133t_copy(tmp_path, monkeypatch):
    # B4: copy only the local sources and bounded real contract AST. Each matrix
    # checks the immediate edge; one separate test runs the real complete chain.
    from .helpers import _authority_fixture_text

    repo = Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(
        runner, "_arch133_parent_security_diagnostic_authority_check", lambda _: ()
    )
    for relative in (
        *runner.ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_authority_fixture_text(repo, relative), encoding="utf-8")
    return tmp_path


def test_133t_real_chain_and_source_only_registration(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_T133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133t"
    assert runner.ACTIVE_CI_CHECKPOINTS[-6:-4] == (_S133_NAME, _T133_NAME)
    assert spec.tests == (
        *runner.ARCH133_L_M_TESTS,
        "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/review_paper/test_arch133_parent_security_diagnostic.py",
        "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_L_M_RUFF_PATHS,
        *runner.ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES,
        "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
        "tests/review_paper/test_arch133_parent_security_diagnostic.py",
        "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parents[1]) == ()
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    for invoke in (runner.preflight_checkpoint, runner.execute_checkpoint):
        with pytest.raises(RuntimeError):
            invoke(spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence")


@pytest.mark.parametrize(
    "relative", tuple(runner.ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS)
)
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133t_complete_local_pins_fail_closed(
    tmp_path, monkeypatch, relative, mutation
):
    root = _133t_copy(tmp_path, monkeypatch)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_parent_policy_diagnostic_authority_check(root)


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
def test_133t_registration_capability_injection_fails_closed(
    tmp_path, monkeypatch, change
):
    root = _133t_copy(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[_T133_NAME] = replace(specs[_T133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_parent_policy_diagnostic_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133t_active_order_drift_fails_closed(tmp_path, monkeypatch, target, mutation):
    root = _133t_copy(tmp_path, monkeypatch)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    if target == "runner":
        line, prior = f'    "{_T133_NAME}",\n', f'    "{_S133_NAME}",\n'
    else:
        line, prior = (
            f"              {_T133_NAME} `\n",
            f"              {_S133_NAME} `\n",
        )
    assert text.count(line) == 1
    if mutation == "order":
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_parent_policy_diagnostic_authority_check(root)


def test_133t_copied_baseline_passes_without_whole_chain_setup(tmp_path, monkeypatch):
    assert (
        runner._arch133_parent_policy_diagnostic_authority_check(
            _133t_copy(tmp_path, monkeypatch)
        )
        == ()
    )


@pytest.mark.parametrize("failure", [(), ("predecessor rejected",)])
def test_133t_predecessor_called_once_and_failure_propagates(monkeypatch, failure):
    root = Path(runner.__file__).resolve().parents[1]
    seen = []

    def previous(repo):
        seen.append(repo)
        return failure

    monkeypatch.setattr(
        runner, "_arch133_parent_security_diagnostic_authority_check", previous
    )
    assert runner._arch133_parent_policy_diagnostic_authority_check(root) == failure
    assert seen == [root]


@pytest.mark.parametrize("mutation", ["inventory", "registration"])
def test_133t_pin_inventory_and_source_registration_drift(
    tmp_path, monkeypatch, mutation
):
    root = _133t_copy(tmp_path, monkeypatch)
    if mutation == "inventory":
        monkeypatch.setattr(runner, "ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES", ())
    else:
        path = root / "scripts/checkpoint_runner.py"
        text = path.read_text(encoding="utf-8")
        # Mutate only the T capability in the copied source contract.
        start = text.index(f'"{_T133_NAME}": CheckpointSpec(')
        text = text[:start] + text[start:].replace(
            "preflight=None", "preflight=unreviewed", 1
        )
        path.write_text(text, encoding="utf-8")
    assert runner._arch133_parent_policy_diagnostic_authority_check(root)
