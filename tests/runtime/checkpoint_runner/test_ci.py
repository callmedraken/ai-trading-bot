from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _EXPECTED_RETAINED_CHECKPOINTS,
    _clean_source,
    _event,
    _outcome,
)


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["docs/foo.md"], "DOCS_ONLY"),
        (["docs/foo.md", "docs/nested/bar.md"], "DOCS_ONLY"),
        (["docs/foo.md", "src/foo.py"], "FULL"),
        (["docs/foo.md", "tests/foo.py"], "FULL"),
        ([".github/workflows/checkpoint-source-gates.yml"], "FULL"),
        (["scripts/checkpoint_runner.py"], "FULL"),
        (["pyproject.toml"], "FULL"),
        (["unknown"], "FULL"),
        ([], "FULL"),
        ([""], "FULL"),
        (["docs/../src/foo.py"], "FULL"),
        (["docs/"], "FULL"),
        ([" docs/foo.md"], "FULL"),
        (["docs\\foo.md"], "FULL"),
    ],
)
def test_docs_changed_path_classification(paths, expected):
    assert runner.classify_changed_paths(paths) == expected


@pytest.mark.parametrize("name", ["push", "pull_request"])
def test_ci_classification_uses_exact_event_base_and_nul_paths(
    tmp_path, monkeypatch, name
):
    base, head = "a" * 40, "b" * 40
    _event(monkeypatch, tmp_path, base, name)
    calls = []

    def git(repo, *args):
        calls.append(args)
        return "commit" if args[0] == "cat-file" else ""

    monkeypatch.setattr(runner, "_git_output", git)

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv, 0, b"docs/a file.md\x00docs/nested.md\x00", b""
        )

    monkeypatch.setattr(runner.subprocess, "run", run)
    result = runner._ci_changes(tmp_path, head)
    assert result["mode"] == "DOCS_ONLY"
    assert result["changed_paths"] == ["docs/a file.md", "docs/nested.md"]
    assert calls == [
        ("cat-file", "-t", base),
        ("merge-base", "--is-ancestor", base, head),
        ("git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"),
    ]


@pytest.mark.parametrize(
    "base", [None, "", "0" * 40, "invalid", "g" * 40, "--malicious", 123]
)
def test_ci_invalid_base_falls_back_without_git(tmp_path, monkeypatch, base):
    _event(monkeypatch, tmp_path, base)
    monkeypatch.setattr(
        runner, "_git_output", lambda *a: pytest.fail("invalid base used")
    )
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "bad_event", ["[]", "null", "{}", "{", '{"pull_request": null}']
)
def test_ci_missing_or_malformed_event_falls_back(tmp_path, monkeypatch, bad_event):
    event = _event(monkeypatch, tmp_path, "a" * 40, "pull_request")
    event.write_text(bad_event)
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize("stage", ["cat-file", "merge-base"])
def test_ci_unavailable_base_or_nonancestor_falls_back(tmp_path, monkeypatch, stage):
    _event(monkeypatch, tmp_path, "a" * 40)

    def git(repo, *args):
        if args[0] == stage:
            raise RuntimeError("unavailable")
        return "commit"

    monkeypatch.setattr(runner, "_git_output", git)
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"", 0),
        (b" docs/hidden.md\x00", 0),
        (b"docs/a.md", 0),
        (b"docs/a.md\x00", 1),
        (b"docs/a.md\x00src/old.py\x00", 0),
    ],
)
def test_ci_unknown_diff_and_moved_source_fall_back(tmp_path, monkeypatch, raw, code):
    _event(monkeypatch, tmp_path, "a" * 40)
    monkeypatch.setattr(runner, "_git_output", lambda *a: "commit")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, code, raw, b""),
    )
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "docs_only,mode,exit_code,drift,expected",
    [
        (False, "DOCS_ONLY", 0, False, True),
        (False, "FULL", 0, False, True),
        (True, "DOCS_ONLY", 0, False, True),
        (True, "DOCS_ONLY", 1, False, False),
        (True, "FULL", 0, False, False),
        (True, "DOCS_ONLY", 0, True, False),
        (False, "DOCS_ONLY", 0, True, False),
    ],
)
def test_ci_docs_gate_evidence_range_check_and_output(
    tmp_path, monkeypatch, docs_only, mode, exit_code, drift, expected
):
    states = iter(
        [_clean_source(), {**_clean_source(), "porcelain": "?? drift" if drift else ""}]
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: next(states))
    monkeypatch.setattr(
        runner,
        "_ci_changes",
        lambda *a: {
            "mode": mode,
            "base": "c" * 40,
            "changed_paths": ["docs/a.md"],
            "reason": "test",
        },
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    calls = []

    def execute(step, **kwargs):
        calls.append(step.argv)
        return _outcome(step.name, exit_code)

    monkeypatch.setattr(runner, "_execute_step", execute)
    passed, path = runner.verify_ci_changes(
        repo_root=tmp_path, evidence_root=tmp_path / "evidence", docs_only=docs_only
    )
    assert passed == expected
    assert calls == (
        [("git", "diff", "--check", "c" * 40, "a" * 40, "--")]
        if docs_only and mode == "DOCS_ONLY"
        else []
    )
    report = json.loads(path.read_text())
    assert report["status"] == ("PASS" if expected else "FAIL")
    assert report["identity_stable"] == (not drift)
    assert report["production_effects"] == "NOT_RUN"
    if docs_only:
        assert not output.exists()
    else:
        assert output.read_text() == f"mode={mode if expected else 'FULL'}\n"


def test_docs_gate_rejects_dirty_source(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner,
        "_git_state",
        lambda repo: {**_clean_source(), "porcelain": " M docs/a.md"},
    )
    monkeypatch.setattr(
        runner, "_ci_changes", lambda *a: pytest.fail("classified dirty source")
    )
    with pytest.raises(RuntimeError, match="clean worktree"):
        runner.verify_ci_changes(
            repo_root=tmp_path, evidence_root=tmp_path / "evidence", docs_only=True
        )


def test_ci_workflow_fast_route_full_fallback_and_slim_artifacts():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert runner._batch_workflow_is_reviewed(workflow)
    assert "workflow_dispatch:" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
    assert workflow.count("verify-batch @Checkpoints") == 2
    assert workflow.count('verify "${{ steps.route.outputs.checkpoint }}"') == 1
    assert workflow.count('verify "${{ needs.source-static.outputs.checkpoint }}"') == 1
    assert workflow.count("AI_TRADING_BOT_SOURCE_GATE_PHASE: static") == 2
    assert workflow.count("AI_TRADING_BOT_SOURCE_GATE_PHASE: tests") == 2
    assert "shard: [0, 1, 2, 3]" in workflow
    assert "resolve_ci_checkpoint(" in workflow
    assert (
        "  source-gates:\n"
        "    needs: [source-static, active-tests, full-tests, certification-tests]\n"
        "    if: always()\n" in workflow
    )
    assert "resolve_ci_certification_profile(" in workflow
    assert workflow.count("  certification-tests:\n") == 1
    assert ".\\scripts\\run_test_certification.py `" in workflow
    assert "CANONICAL_CERTIFICATION_WALL_SECONDS=" in workflow
    assert "- name: Require source gate success" in workflow
    assert workflow.index("classify-ci") < workflow.index(
        "Verify active checkpoint static authority"
    )
    assert (
        "- name: Validate docs-only range\n"
        "        if: steps.changes.outputs.mode == 'DOCS_ONLY'" in workflow
    )
    assert "-File .\\ops.ps1 verify-docs" in workflow
    assert workflow.count("/**/pytest-results.xml") == 2
    assert "!${{ runner.temp }}/ai-trading-bot-checkpoints/**/pytest/**" in workflow


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "comment",
        "exit",
        "rename",
        "reverse",
        "concurrency",
        "aggregator",
        "shards",
    ],
)
def test_batch_workflow_authority_rejects_incomplete_or_ambiguous_invocation(mutation):
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    if mutation == "duplicate":
        workflow += "\nverify-batch @Checkpoints\n"
    elif mutation == "comment":
        workflow = workflow.replace(
            "    arch131-robinhood-review-paper",
            "    # arch131-robinhood-review-paper",
        )
    elif mutation == "exit":
        workflow = workflow.replace(
            "verify-batch @Checkpoints\n          exit $LASTEXITCODE",
            "verify-batch @Checkpoints\n          exit 0",
            1,
        )
    elif mutation == "rename":
        workflow = workflow.replace(
            "arch131-robinhood-review-paper", "missing-checkpoint"
        )
    elif mutation == "reverse":
        workflow = (
            workflow.replace("arch131-robinhood-review-paper", "TEMP")
            .replace("arch131-robinhood-mcp-schema", "arch131-robinhood-review-paper")
            .replace("TEMP", "arch131-robinhood-mcp-schema")
        )
    elif mutation == "concurrency":
        workflow = workflow.replace(
            "cancel-in-progress: true", "cancel-in-progress: false"
        )
    elif mutation == "aggregator":
        workflow = workflow.replace(
            "  source-gates:\n"
            "    needs: [source-static, active-tests, full-tests, "
            "certification-tests]\n"
            "    if: always()\n",
            "  source-gates:\n"
            "    needs: [source-static, active-tests, full-tests, "
            "certification-tests]\n"
            "    if: success()\n",
        )
    else:
        workflow = workflow.replace("shard: [0, 1, 2, 3]", "shard: [0, 1]")
    assert not runner._batch_workflow_is_reviewed(workflow)


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
@pytest.mark.parametrize(
    "scenario", ["docs", "whitespace", "moved_source", "unavailable"]
)
def test_ci_change_gate_against_real_git_range(
    tmp_path, monkeypatch, event_name, scenario
):
    repo = tmp_path / "repository"
    repo.mkdir()

    def git(*args):
        result = subprocess.run(
            ("git", *args), cwd=repo, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "CI test")
    git("config", "user.email", "ci-test@example.invalid")
    git("config", "core.autocrlf", "false")
    (repo / "docs").mkdir()
    (repo / "src").mkdir()
    (repo / "docs/a.md").write_text("before\n", encoding="utf-8", newline="\n")
    (repo / "src/source.py").write_text("source\n", encoding="utf-8", newline="\n")
    git("add", "docs/a.md", "src/source.py")
    git("commit", "--quiet", "-m", "base")
    base = git("rev-parse", "HEAD")
    if scenario == "moved_source":
        git("mv", "src/source.py", "docs/source.py")
    else:
        (repo / "docs/a.md").write_text(
            "after  \n" if scenario == "whitespace" else "after\n",
            encoding="utf-8",
            newline="\n",
        )
    git("add", "docs/a.md")
    git("commit", "--quiet", "-m", "change")
    _event(
        monkeypatch,
        tmp_path,
        "f" * 40 if scenario == "unavailable" else base,
        event_name,
    )
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    mode = runner._ci_changes(repo, git("rev-parse", "HEAD"))["mode"]
    assert mode == (
        "FULL" if scenario in {"moved_source", "unavailable"} else "DOCS_ONLY"
    )
    passed, path = runner.verify_ci_changes(
        repo_root=repo, evidence_root=tmp_path / "evidence", docs_only=True
    )
    assert passed == (scenario == "docs")
    report = json.loads(path.read_text())
    assert report["source_before"] == report["source_after"]
    assert report["identity_stable"] is True
    assert report["status"] == ("PASS" if passed else "FAIL")
    assert git("status", "--porcelain=v1", "--untracked-files=all") == ""


def test_r2a_workflow_scope_and_narrow_branch_trigger():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    branches = workflow.split("    branches:\n", 1)[1].split("  pull_request:", 1)[0]
    assert tuple(
        line.strip().removeprefix("- ").strip('"')
        for line in branches.splitlines()
        if line.strip()
    ) == (
        "develop",
        "feature/d10c-durable-wake-evidence",
        "feature/d10c-r8-terminal-halt",
        "feature/d10c-r8-incident-reconciliation",
        "feature/robinhood-*",
        "feature/test-suite-*",
    )
    for name in _EXPECTED_RETAINED_CHECKPOINTS:
        assert name not in workflow
        modified = workflow.replace(
            "  AI_TRADING_BOT_ACTIVE_CHECKPOINTS: >-\n",
            f"  AI_TRADING_BOT_ACTIVE_CHECKPOINTS: >-\n    {name}\n",
        )
        assert not runner._batch_workflow_is_reviewed(modified)


def test_runtime_admission_checkpoint_is_first_and_source_only():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    name = "arch133-robinhood-supervised-runtime-host-admission"
    assert runner.ACTIVE_CI_CHECKPOINTS[2] == name
    assert workflow.count(name) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.tests == runner.SUPERVISED_RUNTIME_ADMISSION_TESTS
    assert spec.authority_check is runner._supervised_runtime_admission_authority_check


def test_installation_checkpoint_is_in_exact_ci_batch_and_has_no_effect_dispatch():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    name = "arch133-robinhood-supervised-release-installation"
    assert runner.ACTIVE_CI_CHECKPOINTS[4] == name
    assert workflow.count(f"              {name} `\n") == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.tests == runner.SUPERVISED_RELEASE_INSTALLATION_TESTS
    assert (
        spec.authority_check is runner._supervised_release_installation_authority_check
    )


@pytest.mark.parametrize(
    "old,new",
    [
        pytest.param(
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
            "needs.source-static.outputs.route == 'ACTIVE'",
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY'",
            id="active-route",
        ),
        pytest.param(
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
            "needs.source-static.outputs.certification_profile == ''",
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY'",
            id="profile-skips-broad",
        ),
        pytest.param(
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
            "needs.source-static.outputs.certification_profile != ''",
            "if: needs.source-static.outputs.mode != 'DOCS_ONLY'",
            id="profile-certification-condition",
        ),
        pytest.param(
            'elif [ "$ROUTE" = "ACTIVE" ] && [ -n "$CERT_PROFILE" ]; then\n'
            '            test "$ACTIVE_RESULT" = "success"\n'
            '            test "$FULL_RESULT" = "skipped"\n'
            '            test "$CERT_RESULT" = "success"',
            'elif [ "$ROUTE" = "ACTIVE" ] && [ -n "$CERT_PROFILE" ]; then\n'
            '            test "$ACTIVE_RESULT" = "success"\n'
            '            test "$FULL_RESULT" = "success"\n'
            '            test "$CERT_RESULT" = "skipped"',
            id="profile-aggregate",
        ),
        pytest.param(
            "AI_TRADING_BOT_SOURCE_GATE_SHARD_COUNT: 4",
            "AI_TRADING_BOT_SOURCE_GATE_SHARD_COUNT: 2",
            id="shard-count",
        ),
        pytest.param("shard: [0, 1, 2, 3]", "shard: [0, 1, 2, 3, 4]", id="matrix"),
        pytest.param("fail-fast: false", "fail-fast: true", id="fail-fast"),
        pytest.param(
            "- name: Enforce broad test hygiene budget\n        if: always()",
            "- name: Enforce broad test hygiene budget\n        if: success()",
            id="broad-hygiene-always",
        ),
        pytest.param(
            "if ($Seconds -ge 300)", "if ($Seconds -ge 600)", id="broad-hygiene-budget"
        ),
        pytest.param(
            "- name: Enforce canonical certification hygiene budget\n"
            "        if: always()",
            "- name: Enforce canonical certification hygiene budget\n"
            "        if: success()",
            id="cert-hygiene-always",
        ),
        pytest.param(
            "if ($Wall -ge 300)", "if ($Wall -ge 600)", id="cert-hygiene-budget"
        ),
        pytest.param(
            "CERT_RESULT: ${{ needs.certification-tests.result }}",
            "CERT_RESULT: success",
            id="cert-aggregate-binding",
        ),
        pytest.param("set -euo pipefail", "set +e", id="aggregate-fail-closed"),
    ],
)
def test_broad_push_policy_mutations_fail_closed(old, new):
    repo = Path(runner.__file__).resolve().parents[1]
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(old) == 1
    assert not runner._batch_workflow_is_reviewed(workflow.replace(old, new, 1))


def test_ci_certification_profile_mapping_is_explicit_and_bounded():
    assert runner.CI_CERTIFICATION_PROFILES == {
        "arch134-armed-paper-mvp": "robinhood",
        "arch134-production-paper-runtime": "robinhood",
    }
    assert (
        runner.resolve_ci_certification_profile("arch134-armed-paper-mvp")
        == "robinhood"
    )
    assert (
        runner.resolve_ci_certification_profile(
            "arch134-production-strategy-live-paper"
        )
        is None
    )
    assert runner.resolve_ci_certification_profile(None) is None


def test_reviewed_active_batch_digest_matches_single_canonical_tuple():
    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ACTIVE_CI_CHECKPOINTS"
    ]
    assert len(values) == 1
    assert tuple(ast.literal_eval(values[0])) == runner.ACTIVE_CI_CHECKPOINTS
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 62
    assert len(set(runner.ACTIVE_CI_CHECKPOINTS)) == 62
    assert (
        hashlib.sha256(
            ast.dump(values[0], include_attributes=False).encode("utf-8")
        ).hexdigest()
        == runner.REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
    )
