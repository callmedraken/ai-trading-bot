from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _A133_NAME,
    _A133_SOURCE,
    _A133_TEST,
    _B133_NAME,
    _B133_SOURCES,
    _B133_TEST,
    _C133_NAME,
    _C133_SOURCE,
    _C133_TEST,
    _D133_NAME,
    _D133_SOURCE,
    _D133_TEST,
    _E133_NAME,
    _E133_SOURCES,
    _E133_TEST,
    _G133_NAME,
    _G133_SOURCES,
    _133a_authority_copy,
    _133b_authority_copy,
    _133c_authority_copy,
    _133d_authority_copy,
    _133e_authority_copy,
    _133g_authority_copy,
)


def test_133a_source_only_registration_and_single_ordered_batch():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_A133_NAME]
    assert spec.name == _A133_NAME
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133a"
    assert spec.authority_check is runner._arch133_unattended_activation_authority_check
    assert spec.tests == (*runner.ARCH133_A_G_TESTS, _A133_TEST)
    assert spec.ruff_paths == (*runner.ARCH133_A_G_RUFF_PATHS, _A133_SOURCE, _A133_TEST)
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_A133_NAME) == 1
    index = runner.ACTIVE_CI_CHECKPOINTS.index(_A133_NAME)
    assert runner.ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] == (
        "arch131-robinhood-supervised-qualification",
        _A133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_A133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import sqlite3",
        "import socket",
        "import subprocess",
        "from pathlib import Path",
        "from uuid import uuid4",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.risk.manager import RiskManager",
        "datetime.now(UTC)",
        "open('paper.sqlite', 'w')",
        "sleep(1)",
        "while True:\n    pass",
        "callback()",
    ],
)
def test_133a_authority_pins_every_import_and_call(tmp_path, addition):
    root = _133a_authority_copy(tmp_path)
    path = root / _A133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert "133-A pure activation/wake boundary drift" in (
        runner._arch133_unattended_activation_authority_check(root)
    )


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("source", "missing"),
        ("source", "syntax"),
        ("runner", "missing"),
        ("runner", "registration"),
        ("runner", "batch_missing"),
        ("runner", "batch_duplicate"),
        ("workflow", "missing"),
        ("workflow", "batch_missing"),
        ("workflow", "batch_duplicate"),
    ],
)
def test_133a_authority_fails_closed_on_missing_or_drifting_material(
    tmp_path, target, mutation
):
    root = _133a_authority_copy(tmp_path)
    relative = {
        "source": _A133_SOURCE,
        "runner": "scripts/checkpoint_runner.py",
        "workflow": ".github/workflows/checkpoint-source-gates.yml",
    }[target]
    path = root / relative
    if mutation == "missing":
        path.unlink()
    elif mutation == "syntax":
        path.write_text("def broken(:", encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
        if mutation == "registration":
            start = text.index('        "' + _A133_NAME + '": CheckpointSpec(')
            end = text.index(
                '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
            )
            block = text[start:end].replace("preflight=None", "preflight=_r8_preflight")
            text = text[:start] + block + text[end:]
        else:
            line = (
                f'    "{_A133_NAME}",\n'
                if target == "runner"
                else f"              {_A133_NAME} `\n"
            )
            assert text.count(line) == 1
            text = text.replace(line, "" if mutation == "batch_missing" else line * 2)
        path.write_text(text, encoding="utf-8")
    assert runner._arch133_unattended_activation_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"tests": ()},
        {"ruff_paths": ()},
    ],
)
def test_133a_runtime_registration_drift_is_rejected(tmp_path, monkeypatch, change):

    root = _133a_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_A133_NAME] = replace(specs[_A133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_unattended_activation_authority_check(root)


def test_133b_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_B133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133b"
    assert spec.authority_check is runner._arch133_unattended_state_authority_check
    assert spec.tests == (*runner.ARCH133_A_G_TESTS, _A133_TEST, _B133_TEST)
    assert spec.ruff_paths == (
        *runner.ARCH133_A_G_RUFF_PATHS,
        *_B133_SOURCES,
        _B133_TEST,
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_B133_NAME) == 1
    index = runner.ACTIVE_CI_CHECKPOINTS.index(_B133_NAME)
    assert runner.ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] == (
        _A133_NAME,
        _B133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_B133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


@pytest.mark.parametrize("source", _B133_SOURCES)
@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import socket",
        "import subprocess",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.risk.manager import RiskManager",
        "datetime.now(UTC)",
        "open('paper.sqlite', 'w')",
        "callback()",
        "while True:\n    pass",
    ],
)
def test_133b_authority_pins_every_import_and_call(tmp_path, source, addition):
    root = _133b_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-B closed state boundary drift: {source}" in (
        runner._arch133_unattended_state_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_B133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133b_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133b_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_unattended_state_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133b_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133b_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _B133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch133-robinhood-unattended-one-wake-composition": '
            "CheckpointSpec(",
            start,
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_B133_NAME}",\n'
            if target == "runner"
            else f"              {_B133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_A133_NAME} `\n" + line,
                f"              {_B133_NAME} `\n              {_A133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_unattended_state_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133b_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):

    root = _133b_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_B133_NAME] = replace(specs[_B133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_unattended_state_authority_check(root)


def test_133c_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_C133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133c"
    assert spec.authority_check is runner._arch133_one_wake_authority_check
    assert spec.tests == (
        *runner.ARCH133_A_G_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_A_G_RUFF_PATHS,
        _C133_SOURCE,
        _C133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_C133_NAME) == 1
    start = runner.ACTIVE_CI_CHECKPOINTS.index(_A133_NAME)
    end = runner.ACTIVE_CI_CHECKPOINTS.index(_C133_NAME)
    assert runner.ACTIVE_CI_CHECKPOINTS[start : end + 1] == (
        _A133_NAME,
        _B133_NAME,
        _C133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_C133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import subprocess",
        "import socket",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        (
            "from trading_bot.robinhood_paper_pipeline import "
            "run_robinhood_deterministic_paper_pipeline"
        ),
        (
            "from trading_bot.robinhood_forward_paper_cycle import "
            "run_robinhood_forward_paper_cycle"
        ),
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "effect_seam.simulate_review_paper()",
        "quote_seam.prepare_quote()",
    ],
)
def test_133c_authority_pins_every_import_call_and_edge(tmp_path, addition):
    root = _133c_authority_copy(tmp_path)
    path = root / _C133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-C closed composition boundary drift: {_C133_SOURCE}" in (
        runner._arch133_one_wake_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    [
        _C133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_133c_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133c_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_one_wake_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133c_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133c_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _C133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_C133_NAME}",\n'
            if target == "runner"
            else f"              {_C133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_B133_NAME} `\n" + line,
                f"              {_C133_NAME} `\n              {_B133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_one_wake_authority_check(root)


def test_133d_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_D133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133d"
    assert spec.authority_check is runner._arch133_execution_authority_check
    assert spec.tests == (
        *runner.ARCH133_A_G_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        "tests/test_robinhood_paper_operator.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_A_G_RUFF_PATHS,
        _D133_SOURCE,
        _D133_TEST,
        "src/trading_bot/robinhood_paper_operator.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_D133_NAME) == 1
    index = runner.ACTIVE_CI_CHECKPOINTS.index(_D133_NAME)
    assert runner.ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] == (
        _C133_NAME,
        _D133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_D133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import subprocess",
        "import socket",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        (
            "from trading_bot.robinhood_paper_pipeline import "
            "run_robinhood_deterministic_paper_pipeline"
        ),
        (
            "from trading_bot.robinhood_forward_paper_cycle import "
            "run_robinhood_forward_paper_cycle"
        ),
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "effect_seam.simulate_review_paper()",
        "quote_seam.prepare_quote()",
    ],
)
def test_133d_authority_pins_every_import_call_and_edge(tmp_path, addition):
    root = _133d_authority_copy(tmp_path)
    path = root / _D133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-D closed composition boundary drift: {_D133_SOURCE}" in (
        runner._arch133_execution_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    [
        _D133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_133d_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133d_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133d_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133d_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _D133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_D133_NAME}",\n'
            if target == "runner"
            else f"              {_D133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_C133_NAME} `\n" + line,
                f"              {_D133_NAME} `\n              {_C133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133d_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):

    root = _133d_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_D133_NAME] = replace(specs[_D133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133c_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):

    root = _133c_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_C133_NAME] = replace(specs[_C133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_one_wake_authority_check(root)


def test_133e_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_E133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133e"
    assert spec.authority_check is runner._arch133_host_scheduler_authority_check
    assert spec.tests == (
        *runner.ARCH133_A_G_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        _E133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_A_G_RUFF_PATHS,
        *_E133_SOURCES,
        _E133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_E133_NAME) == 1
    index = runner.ACTIVE_CI_CHECKPOINTS.index(_E133_NAME)
    assert runner.ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] == (
        _D133_NAME,
        _E133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_E133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert runner._arch133_host_scheduler_authority_check(repo) == ()


@pytest.mark.parametrize("source", _E133_SOURCES)
@pytest.mark.parametrize(
    "addition",
    [
        "import subprocess",
        "import socket",
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "scheduler.mutate()",
    ],
)
def test_133e_authority_pins_all_host_runtime_scheduler_and_launcher_edges(
    tmp_path, source, addition
):
    root = _133e_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert (
        f"133-E closed composition boundary drift: {source}"
        in runner._arch133_host_scheduler_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_E133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133e_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133e_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_host_scheduler_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133e_runtime_registration_drift_rejected(tmp_path, monkeypatch, change):

    root = _133e_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_E133_NAME] = replace(specs[_E133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_scheduler_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133e_registration_batch_and_workflow_fail_closed(tmp_path, target, mutation):
    root = _133e_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _E133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch133-robinhood-unattended-host-bootstrap": CheckpointSpec(',
            start,
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_E133_NAME}",\n'
            if target == "runner"
            else f"              {_E133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_D133_NAME} `\n" + line,
                f"              {_E133_NAME} `\n              {_D133_NAME}\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_scheduler_authority_check(root)


def test_133g_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_G133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133g"
    assert spec.authority_check is runner._arch133_host_bootstrap_authority_check
    assert spec.tests == (
        *runner.ARCH133_A_G_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        _E133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH133_A_G_RUFF_PATHS,
        *_G133_SOURCES,
        _E133_TEST,
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_G133_NAME) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS[-17:-15] == (_E133_NAME, _G133_NAME)
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_G133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert runner._arch133_host_bootstrap_authority_check(repo) == ()


@pytest.mark.parametrize("source", _G133_SOURCES)
def test_133g_authority_pins_bootstrap_runtime_and_launcher_edges(tmp_path, source):
    root = _133g_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n# drift\n", encoding="utf-8")
    assert (
        f"133-G closed bootstrap boundary drift: {source}"
        in runner._arch133_host_bootstrap_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_G133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133g_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133g_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_host_bootstrap_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133g_runtime_registration_drift_rejected(tmp_path, monkeypatch, change):

    root = _133g_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_G133_NAME] = replace(specs[_G133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_bootstrap_authority_check(root)


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133g_registration_batch_and_workflow_fail_closed(tmp_path, target, mutation):
    root = _133g_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    line = (
        f'    "{_G133_NAME}",\n'
        if target == "runner"
        else f"              {_G133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        text = text.replace(
            f"              {_E133_NAME} `\n" + line,
            f"              {_G133_NAME} `\n              {_E133_NAME}\n",
        )
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_bootstrap_authority_check(root)


@pytest.mark.parametrize(
    "copy,authority",
    [
        (_133a_authority_copy, runner._arch133_unattended_activation_authority_check),
        (_133b_authority_copy, runner._arch133_unattended_state_authority_check),
        (_133c_authority_copy, runner._arch133_one_wake_authority_check),
        (_133d_authority_copy, runner._arch133_execution_authority_check),
        (_133e_authority_copy, runner._arch133_host_scheduler_authority_check),
        (_133g_authority_copy, runner._arch133_host_bootstrap_authority_check),
    ],
)
def test_copied_local_authority_baseline_passes(tmp_path, copy, authority):
    # A-G have no predecessor calls. Prove compact and full runner copies.
    root = copy(tmp_path)
    assert authority(root) == ()
    (root / "scripts/checkpoint_runner.py").write_bytes(
        Path(runner.__file__).read_bytes()
    )
    assert authority(root) == ()
