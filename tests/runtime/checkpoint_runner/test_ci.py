from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import source_authority as ownership

from .helpers import (
    _EXPECTED_RETAINED_CHECKPOINTS,
    _clean_source,
    _event,
    _historical_workflow_view,
    _outcome,
)


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["docs/example.md"], "DOCS_ONLY"),
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
        (["docs//foo.md"], "FULL"),
        (["docs/./foo.md"], "FULL"),
        (["/docs/foo.md"], "FULL"),
        (["docs/foo\x00.md"], "FULL"),
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
def test_ci_invalid_base_or_zero_without_identity_falls_back_without_git(
    tmp_path, monkeypatch, base
):
    _event(monkeypatch, tmp_path, base)
    monkeypatch.setattr(
        runner, "_git_output", lambda *a: pytest.fail("invalid base used")
    )
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


def _first_push_identity(monkeypatch, tmp_path):
    base, head = "a" * 40, "b" * 40
    ref = "refs/heads/feature/test-suite-first-push"
    event = _event(monkeypatch, tmp_path, "0" * 40)
    payload = {
        "before": "0" * 40,
        "after": head,
        "ref": ref,
        "created": True,
        "deleted": False,
        "forced": False,
    }
    event.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_SHA", head)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: base)
    outputs = {
        ("rev-parse", "HEAD"): head,
        ("rev-parse", "--is-shallow-repository"): "false",
        (
            "remote",
            "get-url",
            "origin",
        ): "https://github.com/callmedraken/ai-trading-bot.git",
        ("rev-parse", "refs/remotes/origin/develop"): base,
        ("rev-list", "--parents", "-n", "1", head): f"{head} {base}",
        ("cat-file", "-t", base): "commit",
        ("merge-base", "--is-ancestor", base, head): "",
    }
    monkeypatch.setattr(runner, "_git_output", lambda repo, *a: outputs[a])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(
            argv, 0, b"docs/a.md\x00docs/b.md\x00", b""
        ),
    )
    return base, head, event, payload, outputs


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["docs/a.md", "docs/b.md"], "DOCS_ONLY"),
        (["src/foo.py"], "FULL"),
        (["tests/test_foo.py"], "FULL"),
        ([".github/workflows/checkpoint-source-gates.yml"], "FULL"),
        (["docs/a.md", "src/foo.py"], "FULL"),
        (["unknown"], "FULL"),
        ([], "FULL"),
    ],
)
def test_ci_first_push_exact_develop_child_uses_closed_classifier(
    monkeypatch, tmp_path, paths, expected
):
    base, head, _, _, _ = _first_push_identity(monkeypatch, tmp_path)
    raw = ("\x00".join(paths) + "\x00").encode() if paths else b""

    def diff(argv, **kwargs):
        assert tuple(argv) == (
            "git",
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            base,
            head,
            "--",
        )
        return subprocess.CompletedProcess(argv, 0, raw, b"")

    monkeypatch.setattr(runner.subprocess, "run", diff)
    result = runner._ci_changes(tmp_path, head)
    assert result["mode"] == expected
    assert result["base"] == base
    assert result["changed_paths"] == paths


@pytest.mark.parametrize(
    "mutation",
    [
        "stale_parent",
        "unavailable_develop",
        "tracking_mismatch",
        "missing_tracking",
        "merge",
        "missing_parent",
        "multiple_commits",
        "shallow",
        "missing_head",
        "head_mismatch",
        "sha_mismatch",
        "event_head_mismatch",
        "ref_mismatch",
        "unadmitted_branch",
        "missing_ref",
        "not_created",
        "deleted",
        "forced",
        "malformed_develop",
        "missing_base_object",
        "noncommit_base",
        "ancestry_gap",
        "wrong_origin",
        "malformed_diff",
        "failed_diff",
        "unknown_classifier",
        "nonpush",
    ],
)
def test_ci_first_push_unproven_identity_or_range_stays_full(
    monkeypatch, tmp_path, mutation
):
    base, head, event, payload, outputs = _first_push_identity(monkeypatch, tmp_path)
    parents = ("rev-list", "--parents", "-n", "1", head)
    if mutation in {"stale_parent", "multiple_commits"}:
        outputs[parents] = f"{head} {'c' * 40}"
    elif mutation == "merge":
        outputs[parents] += " " + "c" * 40
    elif mutation == "missing_parent":
        outputs[parents] = head
    elif mutation == "unavailable_develop":

        def unavailable(*a):
            raise RuntimeError("develop unavailable")

        monkeypatch.setattr(runner, "_remote_branch_head", unavailable)
    elif mutation == "malformed_develop":
        monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: "invalid")
    elif mutation == "tracking_mismatch":
        outputs[("rev-parse", "refs/remotes/origin/develop")] = "c" * 40
    elif mutation == "missing_tracking":
        del outputs[("rev-parse", "refs/remotes/origin/develop")]
    elif mutation == "shallow":
        outputs[("rev-parse", "--is-shallow-repository")] = "true"
    elif mutation == "missing_head":
        del outputs[("rev-parse", "HEAD")]
    elif mutation == "head_mismatch":
        outputs[("rev-parse", "HEAD")] = "c" * 40
    elif mutation == "sha_mismatch":
        monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    elif mutation == "event_head_mismatch":
        payload["after"] = "c" * 40
    elif mutation == "ref_mismatch":
        monkeypatch.setenv("GITHUB_REF", "refs/heads/develop")
    elif mutation == "unadmitted_branch":
        payload["ref"] = "refs/heads/feature/other"
        monkeypatch.setenv("GITHUB_REF", payload["ref"])
    elif mutation == "missing_ref":
        del payload["ref"]
    elif mutation in {"not_created", "deleted", "forced"}:
        payload[{"not_created": "created"}.get(mutation, mutation)] = (
            mutation != "not_created"
        )
    elif mutation == "missing_base_object":
        del outputs[("cat-file", "-t", base)]
    elif mutation == "noncommit_base":
        outputs[("cat-file", "-t", base)] = "tree"
    elif mutation == "ancestry_gap":
        del outputs[("merge-base", "--is-ancestor", base, head)]
    elif mutation == "wrong_origin":
        outputs[("remote", "get-url", "origin")] = "https://example.invalid/other"
    elif mutation in {"malformed_diff", "failed_diff"}:
        monkeypatch.setattr(
            runner.subprocess,
            "run",
            lambda argv, **kw: subprocess.CompletedProcess(
                argv, int(mutation == "failed_diff"), b"docs/a.md", b""
            ),
        )
    elif mutation == "unknown_classifier":
        monkeypatch.setattr(runner, "classify_changed_paths", lambda _: "UNKNOWN")
    elif mutation == "nonpush":
        monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    else:
        pytest.fail("unhandled mutation")
    event.write_text(json.dumps(payload))
    assert runner._ci_changes(tmp_path, head)["mode"] == "FULL"


def test_768_first_push_real_git_matches_local_docs_admission(monkeypatch, tmp_path):
    root = tmp_path / "source"
    root.mkdir()

    def git(*args):
        return subprocess.run(
            ("git", *args), cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Routing Test")
    git("config", "user.email", "routing@example.invalid")
    git("remote", "add", "origin", "https://github.com/callmedraken/ai-trading-bot.git")
    (root / "docs").mkdir()
    for name in ("PROJECT_STATUS.md", "AI_TRADING_BOT_HANDOFF.md"):
        (root / "docs" / name).write_text("base\n")
    git("add", "--", "docs/PROJECT_STATUS.md", "docs/AI_TRADING_BOT_HANDOFF.md")
    git("commit", "-m", "develop")
    base = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/develop", base)
    git("checkout", "-b", "feature/test-suite-routing-regression")
    for name in ("PROJECT_STATUS.md", "AI_TRADING_BOT_HANDOFF.md"):
        (root / "docs" / name).write_text("closeout\n")
    git("add", "--", "docs/PROJECT_STATUS.md", "docs/AI_TRADING_BOT_HANDOFF.md")
    git("commit", "-m", "docs closeout")
    head = git("rev-parse", "HEAD")
    ref = "refs/heads/feature/test-suite-routing-regression"
    event = _event(monkeypatch, tmp_path, "0" * 40)
    event.write_text(
        json.dumps(
            {
                "before": "0" * 40,
                "after": head,
                "ref": ref,
                "created": True,
                "deleted": False,
                "forced": False,
            }
        )
    )
    monkeypatch.setenv("GITHUB_SHA", head)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setattr(runner, "_REPOSITORY_ROOT", root)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: base)
    local = runner._prepublication_source(root)
    ci = runner._ci_changes(root, head)
    assert local.failures == ()
    assert local.mode == ci["mode"] == "DOCS_ONLY"
    assert (
        list(local.changed_paths)
        == ci["changed_paths"]
        == ["docs/AI_TRADING_BOT_HANDOFF.md", "docs/PROJECT_STATUS.md"]
    )
    assert local.base_head == ci["base"] == base


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
    assert runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))
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
        "    needs: [source-static, active-tests, full-tests, certification-tests, "
        "certification-full]\n"
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
    from scripts.distributed_full import predecessor_workflow

    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    workflow = predecessor_workflow(workflow)
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
    assert not runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))


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
        "feature/research-*",
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
    assert runner.ACTIVE_CI_CHECKPOINTS[5] == name
    assert workflow.count(name) == 1
    assert runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.tests == runner.SUPERVISED_RUNTIME_ADMISSION_TESTS
    assert spec.authority_check is runner._supervised_runtime_admission_authority_check


def test_installation_checkpoint_is_in_exact_ci_batch_and_has_no_effect_dispatch():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    name = "arch133-robinhood-supervised-release-installation"
    assert runner.ACTIVE_CI_CHECKPOINTS[7] == name
    assert workflow.count(f"              {name} `\n") == 1
    assert runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))
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
            "needs.source-static.outputs.certification_profile == '' && "
            "needs.source-static.outputs.reuse_certification != 'true'",
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
    from scripts.distributed_full import predecessor_workflow

    repo = Path(runner.__file__).resolve().parents[1]
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    workflow = predecessor_workflow(workflow)
    assert workflow.count(old) == 1
    assert not runner._batch_workflow_is_reviewed(workflow.replace(old, new, 1))


def test_ci_certification_profile_mapping_is_explicit_and_bounded():
    assert runner.CI_CERTIFICATION_PROFILES == {
        runner.ARCH147_P4_NAME: "full",
        runner.ARCH147_NAME: "full",
        runner.ARCH146_PARTIAL_STATE_NAME: "full",
        runner.ARCH146_PRE_B2_NAME: "full",
        runner.ARCH146B1_NAME: "full",
        runner.READONLY_ADMISSION_NAME: "robinhood",
        runner.ARCH134_READONLY_DIAGNOSTIC_NAME: "robinhood",
        runner.ARCH134_READONLY_DIAGNOSTIC_R1_NAME: "robinhood",
        runner.ARCH134_READONLY_DIAGNOSTIC_R2_NAME: "robinhood",
        runner.ARCH134_READONLY_DIAGNOSTIC_R3_NAME: "robinhood",
        runner.ARCH146A_NAME: "full",
        runner.ARCH134_FRESH_NAME: "robinhood",
        runner.ARCH134_ACL_NAME: "robinhood",
        runner.ARCH134_D1S4_NAME: "robinhood",
        runner.ARCH134_R5_NAME: "robinhood",
        "arch134-f1r1-d1s3-successor-release-installation-operator": "robinhood",
        "arch134-f1r1-d1s2-successor-installed-readiness": "robinhood",
        "arch134-f1r1-d1s1-successor-soak-source": "robinhood",
        "arch134-f1-five-session-soak": "robinhood",
        "arch134-d1r8-d1-session-execution-consumer": "robinhood",
        "arch134-d1r7-d1-session-authorization": "robinhood",
        "arch134-d1r6-overnight-wake-arming": "robinhood",
        "arch134-d1r5-pre-market-wake-qualification": "robinhood",
        "arch134-alpaca-authentication-qualification": "robinhood",
        "arch134-armed-paper-mvp": "robinhood",
        "arch134-f1r1-b-host-qualification": "robinhood",
        "arch134-f1r1-c1-qualification-operator": "robinhood",
        "arch134-production-paper-runtime": "robinhood",
        "arch134-production-paper-runtime-acl": "robinhood",
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
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 80
    assert len(set(runner.ACTIVE_CI_CHECKPOINTS)) == 80
    assert (
        hashlib.sha256(
            ast.dump(values[0], include_attributes=False).encode("utf-8")
        ).hexdigest()
        == runner.REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
    )


@pytest.mark.parametrize(
    "name,digest",
    [
        (
            "ARCH134_ARMED_PAPER_SOURCE_PINS",
            "53dbbc49e50ecb94659b32e7280225be4cd16893b4d787a1f2aec3a960f5327b",
        ),
        (
            "ARCH134_ARMED_PAPER_IMPORTS",
            "44360941702468b9ff64ae7590925584dadfe918836585a463c509cfac7f53fc",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS",
            "dae912a803d8907587ca1f75f6183e7492404713d78de28708c70305078f93a7",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS",
            "c1fa7ca10e3f5290d9ca5a59d2d37659482dae8cdc8a1039fb901df561cd4b44",
        ),
        (
            "ARCH134_RUNTIME_ACL_SOURCE_PINS",
            "d0afa4f6c071cb7a1883c3089b49eda97cd993100bcc17b5c9d3518dd91d9354",
        ),
        (
            "ARCH134_RUNTIME_ACL_IMPORTS",
            "a8649856d3e25f5edd33b5ce52cc7bb4349cd862985ef7e7e6dd84f0687c1263",
        ),
        (
            "ARCH134_RUNTIME_ACL_AST_PINS",
            "367c40b729e8f149ec4c0d2e63d8c9d18db51befb214e83a0e9d26d0c70d429b",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES",
            "e30e003129212123771fad4326f24862e074d982126a274f660bf2d31b5d6ba5",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES",
            "d0cb70147df26eb7e489f4009cb8144223f529bb1396619adbe0dcedc2930aff",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS",
            "339c6ca847760c421ae536585728c9deced55a7f769b592fb2d9019d2892ca6f",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS",
            "8223c3f7ba506bfb3b69be5b9e59c0466faa4d31ec10ea54104a3f4cd0e80079",
        ),
    ],
)
def test_d1r1_frozen_predecessor_authority_material(name, digest):
    payload = json.dumps(
        getattr(runner, name), sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(payload).hexdigest() == digest


def test_d1r2_exact_successor_overlay_registration_and_frozen_refs(monkeypatch):
    armed = runner.ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES
    assert set(armed) == {
        "src/trading_bot/review_paper/" + name
        for name in (
            "armed_session_store.py",
            "armed_session.py",
            "armed_session_host.py",
        )
    }
    assert set(runner.ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES) == set(armed)
    assert all(
        value != runner.ARCH134_ARMED_PAPER_SOURCE_PINS[path]
        for path, value in armed.items()
    )
    successor = runner.ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS
    diagnostic = "src/trading_bot/review_paper/armed_history_failure.py"
    assert set(successor) == set(
        runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS
    ) | {diagnostic}
    for path, value in runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS.items():
        if path not in armed and path not in {
            "src/trading_bot/review_paper/alpaca_strategy_history.py",
            "tests/review_paper/test_armed_production_paper_session.py",
            "tests/review_paper/test_production_paper_runtime.py",
            "tests/runtime/checkpoint_runner/test_ci.py",
            "tests/runtime/checkpoint_runner/test_core.py",
        }:
            assert successor[path] == value
    specs = runner._checkpoint_specs()
    assert (
        specs[runner.ARCH134_ARMED_PAPER_NAME].remote_branch
        == "feature/robinhood-production-paper-mvp"
    )
    assert (
        specs[runner.ARCH134_RUNTIME_ACL_NAME].remote_branch
        == "feature/robinhood-production-paper-runtime-acl"
    )
    spec = specs[runner.ARCH134_PRODUCTION_PAPER_RUNTIME_NAME]
    assert spec.remote_branch == "feature/robinhood-production-paper-history-recovery"
    assert spec.preflight is spec.execute is None
    assert (
        spec.authority_check is runner._arch134_production_paper_runtime_authority_check
    )
    assert spec.tests == runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_TESTS
    assert (
        spec.ruff_paths == runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_RUFF_PATHS
    )
    assert runner.resolve_ci_checkpoint(specs, spec.remote_branch, "push") == spec.name
    assert (
        runner.resolve_ci_checkpoint(
            specs, "feature/robinhood-production-paper-runtime", "push"
        )
        is None
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "robinhood"
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 80
    assert runner.ACTIVE_CI_CHECKPOINTS[-6:] == (
        runner.ARCH134_ARMED_PAPER_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME,
        runner.ARCH134_PRODUCTION_PAPER_RUNTIME_NAME,
        runner.ARCH134_RUNTIME_ACL_NAME,
    )
    assert (
        runner._arch146a_predecessor_active_digest()
        == runner.ARCH134_FRESH_ACTIVE_SHA256
    )
    root = Path(runner.__file__).resolve().parents[1]
    historical = runner._batch_workflow_is_reviewed
    monkeypatch.setattr(
        runner,
        "_batch_workflow_is_reviewed",
        lambda workflow: historical(_historical_workflow_view(workflow)),
    )
    original_blob = runner._git_blob_sha1
    historical_test_ci = "tests/runtime/checkpoint_runner/test_ci.py"
    historical_test_core = "tests/runtime/checkpoint_runner/test_core.py"
    historical_test_helpers = "tests/scripts/certification_runner/helpers.py"
    historical_test_profiles = "tests/scripts/certification_runner/test_profiles.py"
    historical_test_lanes = "tests/scripts/certification_runner/test_lanes.py"
    historical_test_runtime = "tests/review_paper/test_production_paper_runtime.py"
    historical_test_runtime_acl = (
        "tests/review_paper/test_production_paper_runtime_acl.py"
    )
    monkeypatch.setattr(
        runner,
        "_git_blob_sha1",
        lambda path: (
            runner.READONLY_BLOB_AFTER[historical_test_ci]
            if path == root / historical_test_ci
            else runner.READONLY_BLOB_AFTER[historical_test_core]
            if path == root / historical_test_core
            else "5370ea55565b5981d8fe85d7247c795f72ca3ff5"
            if path == root / historical_test_helpers
            else "d22e2f9fbf0c03c1e6be8aa157d4575e9a517ede"
            if path == root / historical_test_profiles
            else "6ef03c56497055a8edf7d2378c87c44d55800b53"
            if path == root / historical_test_lanes
            else "a48f763db9c6b7a8fd64d787a16c378cc5cbc6c4"
            if path == root / historical_test_runtime
            else "a77edf7dfdaa2e6932594ae77601203f975bbff2"
            if path == root / historical_test_runtime_acl
            else original_blob(path)
        ),
    )
    for check in (
        runner._arch134_armed_paper_authority_check,
        runner._arch134_production_paper_runtime_authority_check,
        runner._arch134_runtime_acl_authority_check,
    ):
        assert check(root) == ()
    for branch, head, tree in [
        (
            "feature/robinhood-production-paper-runtime",
            "6bf8753b0cc8950ae27b32b6858b64d454c512f0",
            "ce3feb2ac48e7aebc23970142aafed5059c447e7",
        ),
        (
            "feature/robinhood-production-paper-runtime-acl",
            "2f122958366d1db282fea51abbd461b83fa893d9",
            "c3fb82add37bdbea12ebad9836ca10000b924fe1",
        ),
    ]:
        # Verify retained refs when a CI checkout includes the frozen branches.
        ref = "refs/remotes/origin/" + branch
        present = subprocess.run(
            ["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref],
            capture_output=True,
        )
        if present.returncode == 0:
            assert runner._git_output(root, "rev-parse", ref) == head
            assert runner._git_output(root, "rev-parse", ref + "^{tree}") == tree


@pytest.mark.parametrize(
    "which",
    [
        "armed_pin",
        "armed_import",
        "runtime_pin",
        "runtime_import",
        "new_pin",
        "unreviewed_armed",
        "unreviewed_runtime",
    ],
)
def test_d1r2_successor_authority_drift_fails_closed(monkeypatch, which):
    root = Path(runner.__file__).resolve().parents[1]
    path = "src/trading_bot/review_paper/armed_session.py"
    if which in {"armed_pin", "unreviewed_armed"}:
        values = dict(runner.ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES)
        values[
            path
            if which == "armed_pin"
            else "src/trading_bot/review_paper/production_paper_runtime.py"
        ] = "0" * 40
        monkeypatch.setattr(
            runner, "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES", values
        )
    elif which == "armed_import":
        values = dict(runner.ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES)
        values[path] = (*values[path], "unreviewed")
        monkeypatch.setattr(
            runner, "ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES", values
        )
    elif which in {"runtime_pin", "new_pin", "unreviewed_runtime"}:
        values = dict(runner.ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS)
        target = (
            "src/trading_bot/review_paper/armed_history_failure.py"
            if which == "new_pin"
            else "src/trading_bot/review_paper/production_paper_runtime.py"
            if which == "unreviewed_runtime"
            else path
        )
        values[target] = "0" * 40
        monkeypatch.setattr(
            runner, "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS", values
        )
    else:
        values = dict(runner.ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS)
        values[path] = (*values[path], "unreviewed")
        monkeypatch.setattr(
            runner, "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS", values
        )
    assert runner._arch134_production_paper_runtime_authority_check(root)


def test_arch146a_registration_and_additive_successor_authority(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH146A_NAME]
    assert spec.remote_branch == runner.ARCH146A_BRANCH
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "full"
    assert "tests/experiments/test_historical_research_dataset.py" in spec.tests
    # Architecture 146-A remains a strict historical contract check.  Its
    # aggregate success predicate is intentionally not a current-topology
    # assertion now that Architecture 147 owns the current research route.
    assert runner._arch134_r5_authority_check(root) == ()
    assert (
        runner._arch146a_predecessor_active_inventory()
        == runner.ACTIVE_CI_CHECKPOINTS[2:]
    )
    assert (
        runner._arch146a_predecessor_active_digest()
        == runner.ARCH134_FRESH_ACTIVE_SHA256
    )
    for key, pin in runner.ARCH146A_AST_PREDECESSORS.items():
        expected = runner.ARCH132_R3M_C3_AST_PINS.get(
            key, runner.ARCH146A_AST_PINS[key]
        )
        assert runner._arch146a_overlay(key, pin, ast_pin=True) == expected
        with pytest.raises(ValueError, match="predecessor"):
            runner._arch146a_overlay(key, "0" * 64, ast_pin=True)


def test_arch146a_successor_maps_fail_closed(monkeypatch):
    monkeypatch.setattr(runner, "ARCH146A_MAPS_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="map"):
        runner._arch146a_maps()
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch146a_authority_check(root)


def test_arch146a_source_mutation_is_rejected(tmp_path):
    root = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH146A_SOURCE_PINS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (root / relative).read_text(encoding="utf-8") + "\n# mutation\n"
        )
    target = tmp_path / "scripts/checkpoint_runner.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )
    assert runner._arch146a_authority_check(tmp_path)


def test_arch146a_c1_full_dependency_is_declared_conditional_and_fail_closed():
    import tomllib

    root = Path(runner.__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    (requirement,) = config["project"]["optional-dependencies"]["optimization-cpu"]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    step = workflow.split("      - name: Install FULL optimizer dependency\n", 1)[
        1
    ].split("      - name: Run canonical certification profile\n", 1)[0]
    assert "if: needs.source-static.outputs.certification_profile == 'full'" in step
    # CI fixes the fixture-producing backend version inside the supported range.
    assert requirement == "scipy>=1.17,<1.19"
    assert (
        "python -m pip install --disable-pip-version-check "
        '"numpy==2.5.1" "scipy==1.18.0"' in step
    )
    assert "if ($LASTEXITCODE -ne 0)" in step
    assert "python -m pip check\n          exit $LASTEXITCODE" in step
    assert runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))


def test_arch146a_c1_exact_successors_and_frozen_failed_maps(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    runner._arch146a_maps()
    runner._arch146a_c1_maps()
    assert runner._arch132_r3n_c1_arch146a_c2_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH146A_C1_AST_PREDECESSORS, runner.ARCH146A_C1_AST_PINS),
        (False, runner.ARCH146A_C1_BLOB_PREDECESSORS, runner.ARCH146A_C1_BLOB_PINS),
    ):
        for key, pin in before.items():
            assert runner._arch146a_c1_pin(
                key, pin, ast_pin=ast_pin
            ) == runner._arch146a_c2_pin(key, after[key], ast_pin=ast_pin)
            assert runner._arch146a_c1_pin(
                key, after[key], ast_pin=ast_pin
            ) == runner._arch146a_c2_pin(key, after[key], ast_pin=ast_pin)
            with pytest.raises(ValueError, match="C1 wrong exact predecessor"):
                runner._arch146a_c1_pin(key, "0" * len(pin), ast_pin=ast_pin)


def test_arch146a_c1_missing_successor_map_fails_closed(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(runner, "ARCH146A_C1_AST_PINS", {})
    with pytest.raises(ValueError, match="C1 exact successor maps"):
        runner._arch146a_c1_maps()
    assert runner._arch146a_authority_check(root)


def test_arch146a_c2_solver_pin_matches_accepted_fixture_provenance():
    import re

    root = Path(runner.__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/cli/historical-experiment-audit-v3-compact.json"
    identities = set(
        re.findall(r"scipy-highs-[0-9.]+", fixture.read_text(encoding="utf-8"))
    )
    assert identities == {"scipy-highs-1.18.0"}
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert '"numpy==2.5.1" "scipy==1.18.0"' in workflow


def test_arch146a_c2_maps_and_wrong_predecessors_fail_closed(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch146a_c2_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH146A_C2_AST_PREDECESSORS, runner.ARCH146A_C2_AST_PINS),
        (False, runner.ARCH146A_C2_BLOB_PREDECESSORS, runner.ARCH146A_C2_BLOB_PINS),
    ):
        for key, pin in before.items():
            assert runner._arch146a_c2_pin(
                key, pin, ast_pin=ast_pin
            ) == runner._arch132_r3m_pin(key, after[key], ast_pin=ast_pin)
            with pytest.raises(ValueError, match="C2 wrong exact predecessor"):
                runner._arch146a_c2_pin(key, "0" * len(pin), ast_pin=ast_pin)
    monkeypatch.setattr(runner, "ARCH146A_C2_BLOB_PINS", {})
    with pytest.raises(ValueError, match="C2 exact successor maps"):
        runner._arch146a_c2_maps()
    assert runner._arch146a_authority_check(root)


# R3M provenance fixtures are synthetic GitHub responses, with no live API dependency.
def _reuse_fixture(profile="full"):
    checkpoint = (
        runner.ARCH146A_NAME if profile == "full" else runner.ARCH134_FRESH_NAME
    )
    branch = runner._checkpoint_specs()[checkpoint].remote_branch
    head, tree, repository_id = "a" * 40, "b" * 40, 123
    repo = {"full_name": "callmedraken/ai-trading-bot", "id": repository_id}
    workflow = {
        "id": 456,
        "name": "Checkpoint Source Gates",
        "path": ".github/workflows/checkpoint-source-gates.yml",
        "state": "active",
    }
    run = {
        "id": 100,
        "run_attempt": 1,
        "repository": repo,
        "head_repository": repo,
        "name": workflow["name"],
        "workflow_id": workflow["id"],
        "path": workflow["path"],
        "head_sha": head,
        "head_branch": branch,
        "event": "push",
        "status": "completed",
        "conclusion": "success",
    }
    required = {
        "source-static": [
            "Resolve source gate route",
            "Verify active checkpoint static authority",
        ],
        "active-tests": ["Verify active checkpoint tests"],
        f"certification-tests ({checkpoint} / {profile})": [
            "Run canonical certification profile",
            "Enforce canonical certification hygiene budget",
        ],
        "full-tests": [],
        "source-gates": ["Require source gate success"],
    }
    jobs = [
        {
            "name": name,
            "run_id": 100,
            "run_attempt": 1,
            "head_sha": head,
            "status": "completed",
            "conclusion": "skipped" if name == "full-tests" else "success",
            "steps": (
                []
                if name == "full-tests"
                else [
                    {
                        "name": step,
                        "status": "completed",
                        "conclusion": "success",
                    }
                    for step in steps
                ]
            ),
        }
        for name, steps in required.items()
    ]
    prefix = "repos/callmedraken/ai-trading-bot"
    runs_path = (
        f"{prefix}/actions/workflows/456/runs?head_sha={head}&event=push&per_page=100"
    )
    jobs_path = f"{prefix}/actions/runs/100/attempts/1/jobs?per_page=100"
    responses = {
        prefix: repo,
        f"{prefix}/actions/workflows/checkpoint-source-gates.yml": workflow,
        f"{prefix}/git/commits/{head}": {"sha": head, "tree": {"sha": tree}},
        f"{prefix}/git/ref/heads/develop": {
            "ref": "refs/heads/develop",
            "object": {"type": "commit", "sha": head},
        },
        runs_path: {"total_count": 1, "workflow_runs": [run]},
        f"{prefix}/actions/runs/100": dict(run),
        jobs_path: {"total_count": len(jobs), "jobs": jobs},
    }
    args = dict(
        head=head,
        tree=tree,
        current_run_id=200,
        repository_id=repository_id,
        lookup=responses.__getitem__,
    )
    return args, responses, run, jobs, runs_path, jobs_path


REAL_738_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures/ci/arch134-readonly-real-738.json"
)


def _real_738_reuse_fixture():
    fixture = json.loads(REAL_738_FIXTURE.read_text(encoding="utf-8"))
    repository = fixture["repository"]
    workflow = fixture["workflow"]
    run = {
        **fixture["run"],
        "repository": repository,
        "head_repository": repository,
    }
    jobs = fixture["jobs"]
    prefix = "repos/callmedraken/ai-trading-bot"
    head = fixture["commit"]["sha"]
    runs_path = (
        f"{prefix}/actions/workflows/{workflow['id']}/runs"
        f"?head_sha={head}&event=push&per_page=100"
    )
    jobs_path = (
        f"{prefix}/actions/runs/{run['id']}/attempts/{run['run_attempt']}"
        "/jobs?per_page=100"
    )
    responses = {
        prefix: repository,
        f"{prefix}/actions/workflows/checkpoint-source-gates.yml": workflow,
        f"{prefix}/git/commits/{head}": {
            "sha": fixture["commit"]["sha"],
            "tree": {"sha": fixture["commit"]["tree"]},
        },
        f"{prefix}/git/ref/heads/develop": fixture["develop"],
        runs_path: {
            "total_count": 1,
            "workflow_runs": [run],
        },
        f"{prefix}/actions/runs/{run['id']}": dict(run),
        jobs_path: {"total_count": len(jobs), "jobs": jobs},
    }
    return (
        {
            "head": head,
            "tree": fixture["commit"]["tree"],
            "current_run_id": run["id"] + 1,
            "repository_id": repository["id"],
            "lookup": responses.__getitem__,
        },
        responses,
        run,
        jobs,
        runs_path,
        jobs_path,
    )


def test_r3n_real_738_mapped_robinhood_metadata_is_reusable():
    args, _, _, jobs, _, _ = _real_738_reuse_fixture()
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["reason"] == "exact_feature_certification"
    assert result["profile"] == "robinhood"
    assert result["run_id"] == 40288823461
    assert result["run_attempt"] == 1
    assert {job["name"] for job in jobs} == {
        "source-static",
        "active-tests",
        (
            "certification-tests (arch134-fresh-successor-readonly-deployment-"
            "admission / robinhood)"
        ),
        "full-tests",
        "source-gates",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "attempt_two",
        "repository",
        "workflow",
        "event",
        "sha",
        "tree",
        "checkpoint",
        "profile",
        "certification_job",
        "active_missing",
        "active_failed",
        "run_step_missing",
        "run_step_failed",
        "hygiene_missing",
        "hygiene_failed",
        "full_executed",
        "duplicate",
        "truncated",
    ],
)
def test_r3n_real_738_mapped_metadata_mutations_fallback(mutation):
    from copy import deepcopy

    args, responses, run, jobs, runs_path, _ = _real_738_reuse_fixture()
    detail = responses["repos/callmedraken/ai-trading-bot/actions/runs/40288823461"]
    certification = next(
        job for job in jobs if job["name"].startswith("certification-tests")
    )
    if mutation == "attempt_two":
        run["run_attempt"] = detail["run_attempt"] = 2
    elif mutation == "repository":
        run["repository"] = detail["repository"] = {"id": 9, "full_name": "wrong/repo"}
    elif mutation == "workflow":
        run["workflow_id"] = detail["workflow_id"] = 9
    elif mutation == "event":
        run["event"] = detail["event"] = "workflow_dispatch"
    elif mutation == "sha":
        run["head_sha"] = detail["head_sha"] = "c" * 40
    elif mutation == "tree":
        responses["repos/callmedraken/ai-trading-bot/git/commits/" + args["head"]][
            "tree"
        ]["sha"] = "c" * 40
    elif mutation == "checkpoint":
        branch = runner._checkpoint_specs()[runner.ARCH146A_NAME].remote_branch
        run["head_branch"] = detail["head_branch"] = branch
    elif mutation == "profile":
        certification["name"] = certification["name"].replace("robinhood", "full")
    elif mutation == "certification_job":
        certification["name"] = "certification-tests (wrong / robinhood)"
    elif mutation == "active_missing":
        jobs.remove(next(job for job in jobs if job["name"] == "active-tests"))
        responses[runs_path]["total_count"] = len(jobs)
    elif mutation == "active_failed":
        next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = (
            "failure"
        )
    elif mutation.startswith("run_step"):
        steps = certification["steps"]
        step = next(
            step
            for step in steps
            if step["name"] == "Run canonical certification profile"
        )
        if mutation == "run_step_missing":
            steps.remove(step)
        else:
            step["conclusion"] = "failure"
    elif mutation.startswith("hygiene"):
        steps = certification["steps"]
        step = next(
            step
            for step in steps
            if step["name"] == "Enforce canonical certification hygiene budget"
        )
        if mutation == "hygiene_missing":
            steps.remove(step)
        else:
            step["conclusion"] = "failure"
    elif mutation == "full_executed":
        full = next(job for job in jobs if job["name"] == "full-tests")
        full["conclusion"] = "success"
    elif mutation == "duplicate":
        responses[runs_path]["workflow_runs"].append(deepcopy(run))
        responses[runs_path]["total_count"] = 2
    else:
        responses[runs_path] = {"workflow_runs": "truncated"}
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def _broad_reuse_fixture(*, registered=False):
    args, responses, run, jobs, runs_path, jobs_path = _reuse_fixture()
    if registered:
        checkpoint = runner.ARCH144C_NAME
        branch = runner._checkpoint_specs()[checkpoint].remote_branch
        assert branch is not None
        assert (
            runner.resolve_ci_checkpoint(runner._checkpoint_specs(), branch, "push")
            == checkpoint
        )
        assert runner.resolve_ci_certification_profile(checkpoint) is None
    else:
        branch = "feature/test-suite-arch132-r3n-unregistered"
    run["head_branch"] = branch
    responses["repos/callmedraken/ai-trading-bot/actions/runs/100"]["head_branch"] = (
        branch
    )
    broad_steps = {
        "source-static": (
            "Resolve source gate route",
            "Prove exact develop certification reuse",
            (
                "Verify active checkpoint static authority"
                if registered
                else "Verify full batch static authority"
            ),
        ),
        "active-tests": (("Verify active checkpoint tests",) if registered else ()),
        **{
            f"full-tests ({index})": (
                "Record broad test shard start",
                "Verify full batch test shard",
                "Enforce broad test hygiene budget",
            )
            for index in range(4)
        },
        runner.REVIEWED_SKIPPED_CERTIFICATION_JOB: (),
        "source-gates": ("Require source gate success",),
    }
    jobs[:] = [
        {
            "name": name,
            "run_id": 100,
            "run_attempt": 1,
            "head_sha": args["head"],
            "status": "completed",
            "conclusion": (
                "skipped"
                if name == runner.REVIEWED_SKIPPED_CERTIFICATION_JOB
                or (name == "active-tests" and not registered)
                else "success"
            ),
            "steps": (
                [
                    {"name": step, "status": "completed", "conclusion": "success"}
                    for step in step_names
                ]
                if step_names
                else None
            ),
        }
        for name, step_names in broad_steps.items()
    ]
    responses[jobs_path]["total_count"] = len(jobs)
    return args, responses, run, jobs, runs_path, jobs_path


@pytest.mark.parametrize("registered", [False, True])
def test_r3n_c4_broad_jobs_match_reviewed_732_topology(registered):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=registered)
    # Independent literal from #732, not a name copied from the implementation.
    certification = (
        "certification-tests (${{ needs.source-static.outputs.checkpoint }} / "
        "${{ needs.source-static.outputs.certification_profile }})"
    )
    expected = {
        "source-static": "success",
        **{f"full-tests ({index})": "success" for index in range(4)},
        certification: "skipped",
        "active-tests": "success" if registered else "skipped",
        "source-gates": "success",
    }
    assert {job["name"]: job["conclusion"] for job in jobs} == expected
    assert all(job["status"] == "completed" for job in jobs)
    assert runner.REVIEWED_SKIPPED_CERTIFICATION_JOB == certification
    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert runner._batch_workflow_is_reviewed(_historical_workflow_view(workflow))
    assert workflow.count(f"    name: {certification}\n") == 1
    assert (
        runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is True
    )


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize(
    "mutation", ["empty_name", "missing", "duplicate", "running", "success", "failure"]
)
def test_r3n_c4_skipped_certification_identity_is_exact(registered, mutation):
    from copy import deepcopy

    args, responses, _, jobs, _, jobs_path = _broad_reuse_fixture(registered=registered)
    certification = next(
        job for job in jobs if job["name"] == runner.REVIEWED_SKIPPED_CERTIFICATION_JOB
    )
    if mutation == "empty_name":
        certification["name"] = "certification-tests ( / )"
    elif mutation == "missing":
        jobs.remove(certification)
    elif mutation == "duplicate":
        jobs.append(deepcopy(certification))
    elif mutation == "running":
        certification.update(status="in_progress", conclusion=None)
    else:
        certification["conclusion"] = mutation
    responses[jobs_path]["total_count"] = len(jobs)
    assert (
        runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is False
    )


@pytest.mark.parametrize("registered", [False, True])
def test_r3n_c4_coherent_broad_attempt_two_is_not_reusable(registered):
    args, responses, run, jobs, _, jobs_path = _broad_reuse_fixture(
        registered=registered
    )
    run["run_attempt"] = 2
    responses["repos/callmedraken/ai-trading-bot/actions/runs/100"]["run_attempt"] = 2
    for job in jobs:
        job["run_attempt"] = 2
    responses[jobs_path.replace("/attempts/1/", "/attempts/2/")] = responses.pop(
        jobs_path
    )
    assert (
        runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is False
    )


def test_current_integration_policy_avoids_routine_pr_but_keeps_pr_protection():
    root = Path(__file__).resolve().parents[3]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    guidance = (root / "docs/AI_DEVELOPMENT_WORKFLOW.md").read_text()
    policy = guidance.split(
        "### Exact-SHA fast-forward integration and PR non-duplication\n", 1
    )[1].split("\n### ", 1)[0]
    assert "  pull_request:\n" in workflow
    for requirement in (
        "exact expected old develop HEAD/tree",
        "no intervening develop change",
        "git merge --ff-only <accepted-feature-SHA>",
        "git push origin develop",
        "Resulting remote develop HEAD must equal the exact accepted feature",
        "tree must equal the accepted feature tree",
        "does not create a PR",
        "PR merge commit is fallback-only",
        "Keep `pull_request` workflow support and protection",
        "does not\ngrant Codex integration authority",
    ):
        assert requirement in policy
    assert "rebase, squash,\namend, force, rewrite the feature SHA" in policy


def test_docs_only_general_admission_regression(monkeypatch):
    root, context = _r3n_admission_fixture(monkeypatch)
    context["changed"] = ("docs/example.md",)
    assert runner.classify_changed_paths(["docs/example.md"]) == "DOCS_ONLY"
    assert runner._arch132_r3n_admission_authority_check(root) == ()


def test_r3n_prepublication_admission_contract():
    parser = runner._parser(runner._checkpoint_specs())
    args = parser.parse_args(["admit"])
    assert args.command == "admit"
    assert runner.REVIEWED_FEATURE_BRANCH_PREFIXES == (
        "feature/robinhood-",
        "feature/research-",
        "feature/test-suite-",
    )
    assert runner.SOURCE_REPOSITORY == "callmedraken/ai-trading-bot"
    assert runner.ARCH132_R3N_ADMISSION_TESTS == (
        "tests/runtime/checkpoint_runner/test_source_authority.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/scripts/certification_runner/test_lanes.py",
    )


def test_prepublication_admission_selects_infrastructure_coherence_tests(
    monkeypatch, tmp_path
):
    base_tests = runner.ARCH132_R3N_ADMISSION_TESTS
    coherence_tests = runner.PREPUBLICATION_INFRASTRUCTURE_COHERENCE_TESTS
    expected = (*base_tests, *coherence_tests)
    assert runner._prepublication_admission_tests(("src/example.py",)) == base_tests
    assert (
        runner._prepublication_admission_tests(("docs/PROJECT_STATUS.md",))
        == base_tests
    )

    required_paths = (
        ".github/workflows/checkpoint-source-gates.yml",
        "pyproject.toml",
        "scripts/checkpoint_runner.py",
        "scripts/run_test_certification.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
        "scripts/distributed_full.py",
        "tests/runtime/checkpoint_runner/test_source_authority.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/scripts/certification_runner/test_lanes.py",
        ("tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic.py"),
        ("tests/experiments/test_research_strategy_production_compatibility.py"),
        "docs/AI_DEVELOPMENT_WORKFLOW.md",
    )
    for path in required_paths:
        selected = runner._prepublication_admission_tests((path,))
        assert selected == expected
        # The real Windows native regression below belongs to this required
        # module, so workflow/generator edits cannot omit it from admission.
        assert "tests/runtime/checkpoint_runner/test_ci.py" in selected

    source = runner.PrepublicationSource(
        candidate={"head": "a" * 40, "tree": "b" * 40},
        base_head="c" * 40,
        base_tree="d" * 40,
        changed_paths=("scripts/checkpoint_runner.py",),
        mode="FULL",
        failures=(),
    )
    monkeypatch.setattr(runner, "_source_gate_phase", lambda: "all")
    monkeypatch.setattr(runner, "_source_gate_shard", lambda: None)
    monkeypatch.setattr(runner, "_prepublication_source", lambda _: source)
    # Admission selection is the behavior under test.  The installed local
    # Ruff may differ from the CI-pinned version, so keep this unit test
    # independent of that environment detail.
    monkeypatch.setattr(
        runner,
        "check_ruff_version",
        lambda *_args, **_kwargs: {"exit_code": 0},
    )
    captured = {}

    def capture(spec, **_kwargs):
        captured["tests"] = spec.tests
        return True, tmp_path / "admission.json"

    monkeypatch.setattr(runner, "verify_checkpoint", capture)
    passed, _ = runner.prepublication_admission(
        repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert passed
    assert captured["tests"] == expected


def _r3n_admission_fixture(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    context = {
        "branch": "feature/test-suite-r3n-c1-example",
        "porcelain": "",
        "origin": "https://github.com/callmedraken/ai-trading-bot.git",
        "remote_head": "b" * 40,
        "object_available": True,
        "is_ancestor": True,
        "merge_base": "b" * 40,
        "changed": ("scripts/checkpoint_runner.py",),
        "authority": (),
    }
    state = {
        "head": "a" * 40,
        "tree": "c" * 40,
        "branch": context["branch"],
        "porcelain": context["porcelain"],
    }

    def git_state(_):
        state.update(
            branch=context["branch"],
            porcelain=context["porcelain"],
        )
        return state.copy()

    def remote_branch_head(_, branch):
        assert branch == "develop"
        return context["remote_head"]

    original_git_output = runner._git_output

    def git_output(_, *arguments):
        if arguments == ("remote", "get-url", "origin"):
            return context["origin"]
        if arguments[:2] == ("rev-parse", "b" * 40 + "^{commit}"):
            return "b" * 40 if context["object_available"] else "d" * 40
        if arguments[:2] == ("rev-parse", "b" * 40 + "^{tree}"):
            return "c" * 40 if context["object_available"] else "d" * 40
        if arguments[:2] == ("merge-base", "--is-ancestor"):
            if not context["is_ancestor"]:
                raise RuntimeError("not an ancestor")
            return ""
        if arguments[:1] == ("merge-base",):
            return context["merge_base"]
        if arguments[:2] == ("diff", "--name-only"):
            return context["changed"]
        return original_git_output(_, *arguments)

    original_run = runner.subprocess.run

    def run(argv, **kwargs):
        if argv[:5] == ("git", "diff", "--name-only", "--no-renames", "-z"):
            assert argv[5:] == (context["remote_head"], state["head"], "--")
            raw = b"".join(path.encode("utf-8") + b"\0" for path in context["changed"])
            return subprocess.CompletedProcess(
                argv, 0, context.get("raw_changed", raw), b""
            )
        if list(argv) == [runner.sys.executable, "-m", "ruff", "--version"]:
            return subprocess.CompletedProcess(argv, 0, "ruff 0.17.3\n", "")
        assert argv[0] == "git", "unexpected Python/host command"
        return original_run(argv, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setattr(runner, "_git_state", git_state)
    monkeypatch.setattr(runner, "_remote_branch_head", remote_branch_head)
    monkeypatch.setattr(runner, "_git_output", git_output)
    monkeypatch.setattr(
        runner, "_arch132_r3m_authority_check", lambda _: context["authority"]
    )
    return root, context


@pytest.mark.parametrize(
    "branch",
    [
        "feature/research-arch146-b-example",
        "feature/robinhood-example",
        "feature/test-suite-example",
    ],
)
def test_r3n_general_prepublication_admission_accepts_reviewed_feature_families(
    monkeypatch, branch
):
    _, context = _r3n_admission_fixture(monkeypatch)
    context["branch"] = branch
    assert (
        runner._arch132_r3n_admission_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "develop",
        "unknown_branch",
        "dirty",
        "wrong_origin",
        "stale_base",
        "diverged_base",
        "not_ancestor",
        "empty_diff",
        "malformed_identity",
        "unavailable_identity",
        "unknown_classification",
        "invalid_topology",
    ],
)
def test_r3n_general_prepublication_admission_rejects_invalid_state(
    monkeypatch, mutation
):
    _, context = _r3n_admission_fixture(monkeypatch)
    if mutation == "develop":
        context["branch"] = "develop"
    elif mutation == "unknown_branch":
        context["branch"] = "feature/other-example"
    elif mutation == "dirty":
        context["porcelain"] = " M scripts/checkpoint_runner.py"
    elif mutation == "wrong_origin":
        context["origin"] = "https://github.com/other/repository.git"
    elif mutation == "stale_base":
        context["object_available"] = False
    elif mutation == "diverged_base":
        context["merge_base"] = "d" * 40
    elif mutation == "not_ancestor":
        context["is_ancestor"] = False
    elif mutation == "empty_diff":
        context["changed"] = ()
    elif mutation == "malformed_identity":
        context["remote_head"] = "malformed"
    elif mutation == "unavailable_identity":

        def unavailable(_, branch):
            assert branch == "develop"
            raise RuntimeError("remote unavailable")

        monkeypatch.setattr(runner, "_remote_branch_head", unavailable)
    elif mutation == "unknown_classification":
        monkeypatch.setattr(runner, "classify_changed_paths", lambda _: "UNKNOWN")
    else:
        monkeypatch.setattr(runner, "_batch_workflow_is_reviewed", lambda _: False)
    assert runner._arch132_r3n_admission_authority_check(
        Path(runner.__file__).resolve().parents[1]
    )


@pytest.mark.parametrize("profile", ["full", "robinhood"])
def test_r3m_exact_feature_certification_reused(profile):
    args, _, _, _, _, _ = _reuse_fixture(profile)
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["head"] == args["head"] and result["tree"] == args["tree"]
    assert result["run_id"] == 100 and result["run_attempt"] == 1
    assert result["profile"] == profile


def test_r3n_exact_feature_broad_source_gate_reused():
    args, _, _, _, _, _ = _broad_reuse_fixture()
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["reason"] == "exact_feature_broad_source_gate"
    assert result["reuse_kind"] == "broad_source_gate"
    assert result["profile"] == ""
    assert result["shards"] == [0, 1, 2, 3]
    assert result["run_attempt"] == 1


def test_r3n_registered_active_broad_source_gate_reused():
    args, _, _, _, _, _ = _broad_reuse_fixture(registered=True)
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["reason"] == "exact_feature_broad_source_gate"
    assert result["reuse_kind"] == "broad_source_gate"
    assert result["route"] == "ACTIVE"
    assert result["profile"] == ""
    assert result["run_attempt"] == 1


def _r3n_route_fixture(route):
    if route == "mapped":
        return _reuse_fixture()
    return _broad_reuse_fixture(registered=route == "registered")


@pytest.mark.parametrize("route", ["mapped", "registered", "unregistered"])
def test_r3n_attempt_two_is_never_reusable(route):
    args, responses, run, _, _, _ = _r3n_route_fixture(route)
    run["run_attempt"] = 2
    responses["repos/callmedraken/ai-trading-bot/actions/runs/100"]["run_attempt"] = 2
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
@pytest.mark.parametrize("mutation", ["missing_shard", "duplicate_shard"])
def test_r3n_broad_shard_cardinality_is_exact(route, mutation):
    from copy import deepcopy

    args, responses, _, jobs, _, jobs_path = _broad_reuse_fixture(
        registered=route == "registered"
    )
    shard = next(job for job in jobs if job["name"] == "full-tests (0)")
    if mutation == "missing_shard":
        jobs.remove(shard)
    else:
        jobs.append(deepcopy(shard))
    responses[jobs_path]["total_count"] = len(jobs)
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_failed_shard_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(job for job in jobs if job["name"] == "full-tests (2)")["conclusion"] = (
        "failure"
    )
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_failed_hygiene_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(job for job in jobs if job["name"] == "full-tests (1)")["steps"][-1][
        "conclusion"
    ] = "failure"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_registered_active_failure_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=True)
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "failure"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_registered_active_skip_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=True)
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "skipped"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_unregistered_active_run_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture()
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "success"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_certification_run_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(
        job for job in jobs if job["name"] == runner.REVIEWED_SKIPPED_CERTIFICATION_JOB
    )["conclusion"] = "success"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize(
    "mutation", ["attempt_two", "missing_shard", "duplicate_shard"]
)
def test_r3n_broad_source_gate_topology_is_exact(mutation):
    from copy import deepcopy

    args, responses, run, jobs, runs_path, jobs_path = _broad_reuse_fixture()
    if mutation == "attempt_two":
        run["run_attempt"] = 2
        responses["repos/callmedraken/ai-trading-bot/actions/runs/100"][
            "run_attempt"
        ] = 2
    elif mutation == "missing_shard":
        jobs.pop(2)
        responses[jobs_path]["total_count"] = len(jobs)
    else:
        jobs.append(deepcopy(jobs[2]))
        responses[jobs_path]["total_count"] = len(jobs)
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize(
    "mutation", ["shard_hygiene", "active_not_skipped", "cert_not_skipped"]
)
def test_r3n_broad_source_gate_execution_contract_is_exact(mutation):
    args, responses, _, jobs, _, _ = _broad_reuse_fixture()
    if mutation == "shard_hygiene":
        jobs[2]["steps"][-1]["conclusion"] = "failure"
    elif mutation == "active_not_skipped":
        jobs[1]["conclusion"] = "success"
    else:
        jobs[6]["conclusion"] = "success"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("mutation", ["ambiguous", "malformed", "unavailable"])
def test_r3n_broad_source_gate_metadata_fail_closed(mutation):
    from copy import deepcopy

    args, responses, run, jobs, runs_path, jobs_path = _broad_reuse_fixture()
    if mutation == "ambiguous":
        other = deepcopy(run)
        other["id"] = 101
        responses[runs_path]["workflow_runs"].append(other)
        responses[runs_path]["total_count"] = 2
    elif mutation == "malformed":
        responses[runs_path] = {"workflow_runs": "bad"}
    else:
        responses[runs_path] = None
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "sha",
        "tree_only",
        "tree",
        "repository",
        "repository_id",
        "head_repository",
        "workflow",
        "workflow_path",
        "event",
        "manual",
        "branch",
        "unregistered",
        "queued",
        "in_progress",
        "failure",
        "cancelled",
        "static_missing",
        "static_failed",
        "aggregate_missing",
        "aggregate_failed",
        "cert_missing",
        "cert_failed",
        "profile",
        "old_unbound_job",
        "active_missing",
        "step_failed",
        "hygiene_missing",
        "job_sha",
        "job_run",
        "job_attempt",
        "duplicate_job",
        "duplicate_step",
        "ambiguous",
        "malformed",
        "unavailable",
        "lookup_failure",
        "truncated_runs",
        "truncated_jobs",
        "run_detail",
        "develop_changed",
        "workflow_metadata",
    ],
)
def test_r3m_ineligible_provenance_falls_back(mutation):
    from copy import deepcopy

    args, responses, run, jobs, runs_path, jobs_path = _reuse_fixture()
    if mutation in {"sha", "tree_only"}:
        run["head_sha"] = "c" * 40  # Same tree never compensates for a different SHA.
    elif mutation == "tree":
        responses[f"repos/callmedraken/ai-trading-bot/git/commits/{args['head']}"][
            "tree"
        ]["sha"] = "c" * 40
    elif mutation in {"repository", "repository_id", "head_repository"}:
        key = "head_repository" if mutation == "head_repository" else "repository"
        run[key] = {"full_name": "wrong/repository", "id": 999}
    elif mutation == "workflow":
        run["workflow_id"] = 999
    elif mutation == "workflow_path":
        run["path"] = ".github/workflows/other.yml"
    elif mutation in {"event", "manual"}:
        run["event"] = "workflow_dispatch" if mutation == "manual" else "pull_request"
    elif mutation in {"branch", "unregistered"}:
        run["head_branch"] = (
            "feature/unreviewed" if mutation == "branch" else "feature/research-unknown"
        )
    elif mutation in {"queued", "in_progress"}:
        run["status"] = mutation
    elif mutation in {"failure", "cancelled"}:
        run["conclusion"] = mutation
    elif mutation.endswith("_missing") and mutation != "hygiene_missing":
        index = {
            "static_missing": 0,
            "active_missing": 1,
            "cert_missing": 2,
            "aggregate_missing": 3,
        }[mutation]
        jobs.pop(index)
        responses[jobs_path]["total_count"] = len(jobs)
    elif mutation.endswith("_failed") and mutation != "step_failed":
        jobs[{"static_failed": 0, "cert_failed": 2, "aggregate_failed": 3}[mutation]][
            "conclusion"
        ] = "failure"
    elif mutation in {"profile", "old_unbound_job"}:
        jobs[2]["name"] = (
            "certification-tests"
            if mutation == "old_unbound_job"
            else jobs[2]["name"].replace(" / full)", " / robinhood)")
        )
    elif mutation == "step_failed":
        jobs[0]["steps"][0]["conclusion"] = "failure"
    elif mutation == "hygiene_missing":
        jobs[2]["steps"].pop()
    elif mutation in {"job_sha", "job_run", "job_attempt"}:
        key = {
            "job_sha": "head_sha",
            "job_run": "run_id",
            "job_attempt": "run_attempt",
        }[mutation]
        jobs[2][key] = "c" * 40 if key == "head_sha" else 999
    elif mutation == "duplicate_job":
        jobs.append(deepcopy(jobs[0]))
        responses[jobs_path]["total_count"] = len(jobs)
    elif mutation == "duplicate_step":
        jobs[0]["steps"].append(deepcopy(jobs[0]["steps"][0]))
    elif mutation == "ambiguous":
        other = deepcopy(run)
        other["id"] = 101
        responses[runs_path]["workflow_runs"].append(other)
        responses[runs_path]["total_count"] = 2
        prefix = "repos/callmedraken/ai-trading-bot/actions/runs/101"
        responses[prefix] = deepcopy(other)
        other_jobs = deepcopy(jobs)
        for job in other_jobs:
            job["run_id"] = 101
        responses[f"{prefix}/attempts/1/jobs?per_page=100"] = {
            "total_count": len(jobs),
            "jobs": other_jobs,
        }
    elif mutation == "malformed":
        responses[runs_path] = {"workflow_runs": "bad"}
    elif mutation == "unavailable":
        responses[runs_path] = None
    elif mutation == "lookup_failure":

        def unavailable(endpoint):
            raise TimeoutError("synthetic unavailable metadata")

        args["lookup"] = unavailable
    elif mutation in {"truncated_runs", "truncated_jobs"}:
        responses[runs_path if mutation == "truncated_runs" else jobs_path][
            "total_count"
        ] = 101
    elif mutation == "run_detail":
        responses["repos/callmedraken/ai-trading-bot/actions/runs/100"][
            "run_attempt"
        ] = 2
    elif mutation == "develop_changed":
        responses["repos/callmedraken/ai-trading-bot/git/ref/heads/develop"]["object"][
            "sha"
        ] = "c" * 40
    else:
        responses[
            (
                "repos/callmedraken/ai-trading-bot/actions/workflows/che"
                "ckpoint-source-gates.yml"
            )
        ]["name"] = "Other workflow"
    result = runner._PRE_DISTRIBUTED_FIND_REUSABLE(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize(
    "mode,event,ref",
    [
        ("DOCS_ONLY", "push", "refs/heads/develop"),
        ("FULL", "pull_request", "refs/pull/1/merge"),
        ("FULL", "workflow_dispatch", "refs/heads/develop"),
        ("FULL", "push", "refs/heads/feature/research-synthetic"),
    ],
)
def test_r3m_other_routes_never_lookup_provenance(
    tmp_path, monkeypatch, mode, event, ref
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setattr(
        runner, "_github_ci_metadata", lambda _: pytest.fail("unexpected API call")
    )
    assert runner.resolve_develop_ci_reuse(tmp_path, mode)["reuse"] is False


def _develop_reuse_context(tmp_path, monkeypatch):
    args, responses, *_ = _distributed_reuse_fixture()
    repo = "callmedraken/ai-trading-bot"
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_REF_NAME": "develop",
        "GITHUB_REPOSITORY": repo,
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKFLOW": "Checkpoint Source Gates",
        "GITHUB_WORKFLOW_REF": (
            f"{repo}/.github/workflows/checkpoint-source-gates.yml@refs/heads/develop"
        ),
        "GITHUB_SHA": args["head"],
        "GITHUB_RUN_ID": "200",
        "GITHUB_REPOSITORY_ID": "123",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    event = {
        "before": "c" * 40,
        "after": args["head"],
        "ref": "refs/heads/develop",
        "forced": False,
        "deleted": False,
    }
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    state = {
        "head": args["head"],
        "tree": args["tree"],
        "branch": "develop",
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda _: state.copy())
    monkeypatch.setattr(
        runner,
        "_git_output",
        lambda _, *a: f"https://github.com/{repo}.git" if a[0] == "remote" else "",
    )
    monkeypatch.setattr(runner, "_github_ci_metadata", responses.__getitem__)
    return state, path, event


def test_r3m_develop_integration_admits_exact_clean_fast_forward(tmp_path, monkeypatch):
    _develop_reuse_context(tmp_path, monkeypatch)
    assert runner.resolve_develop_ci_reuse(tmp_path, "FULL")["reuse"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "head",
        "tree",
        "branch",
        "dirty",
        "origin",
        "forced",
        "deleted",
        "base",
        "ancestry",
        "changed",
    ],
)
def test_r3m_develop_context_mismatch_cannot_reuse(tmp_path, monkeypatch, mutation):
    state, path, event = _develop_reuse_context(tmp_path, monkeypatch)
    if mutation in {"head", "tree"}:
        state[mutation] = "d" * 40
    elif mutation == "branch":
        state["branch"] = "feature/research-synthetic"
    elif mutation == "dirty":
        state["porcelain"] = " M source.py"
    elif mutation == "origin":
        monkeypatch.setattr(runner, "_git_output", lambda *a: "wrong")
    elif mutation in {"forced", "deleted", "base"}:
        event["before" if mutation == "base" else mutation] = (
            "0" * 40 if mutation == "base" else True
        )
        path.write_text(json.dumps(event), encoding="utf-8")
    elif mutation == "ancestry":

        def git(_, *args):
            if args[0] == "merge-base":
                raise RuntimeError("not an ancestor")
            return "https://github.com/callmedraken/ai-trading-bot.git"

        monkeypatch.setattr(runner, "_git_output", git)
    else:
        values = iter([state.copy(), {**state, "tree": "d" * 40}])
        monkeypatch.setattr(runner, "_git_state", lambda _: next(values))
    assert runner.resolve_develop_ci_reuse(tmp_path, "FULL")["reuse"] is False


@pytest.mark.parametrize(
    "old,new",
    [
        ("needs.source-static.outputs.reuse_certification != 'true'", "true"),
        ('test "$REF" = "refs/heads/develop"', "true"),
        ('test "$EVENT" = "push"', "true"),
        ('test "$ROUTE" = "FULL"', "true"),
        ('test -z "$CERT_PROFILE"', "true"),
        (
            "REUSE: ${{ needs.source-static.outputs.reuse_certification }}",
            "REUSE: true",
        ),
        (
            'resolve_develop_ci_reuse(Path.cwd(), os.environ["CHANGE_MODE"])',
            '{"reuse": True}',
        ),
        ("      actions: read", "      actions: write"),
        (
            "name: certification-tests "
            "(${{ needs.source-static.outputs.checkpoint }} / "
            "${{ needs.source-static.outputs.certification_profile }})",
            "name: certification-tests",
        ),
    ],
)
def test_r3m_reuse_workflow_mutations_fail_authority(old, new):
    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count(old) == 1
    assert not runner._batch_workflow_is_reviewed(workflow.replace(old, new, 1))


def test_r3m_exact_successor_authority_and_frozen_certification_source(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch132_r3m_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH132_R3M_AST_PREDECESSORS, runner.ARCH132_R3M_AST_PINS),
        (False, runner.ARCH132_R3M_BLOB_PREDECESSORS, runner.ARCH132_R3M_BLOB_PINS),
    ):
        for key, pin in before.items():
            expected = runner._arch132_r3m_c1_pin(key, after[key], ast_pin=ast_pin)
            expected = runner._arch132_r3m_c3_pin(key, expected, ast_pin=ast_pin)
            if not ast_pin and expected == runner.READONLY_BLOB_BEFORE.get(key):
                expected = runner.READONLY_BLOB_AFTER[key]
            assert runner._arch132_r3m_pin(key, pin, ast_pin=ast_pin) == expected
            with pytest.raises(ValueError, match="R3M wrong exact predecessor"):
                runner._arch132_r3m_pin(key, "0" * len(pin), ast_pin=ast_pin)
    monkeypatch.setattr(runner, "ARCH132_R3M_AST_PINS", {})
    assert runner._arch132_r3m_authority_check(root)


@pytest.mark.parametrize(
    "mode,route,profile,reuse,active,broad,canonical,event,ref,passed",
    [
        (
            "FULL",
            "FULL",
            "",
            "true",
            "skipped",
            "skipped",
            "skipped",
            "push",
            "refs/heads/develop",
            True,
        ),
        (
            "FULL",
            "FULL",
            "",
            "false",
            "skipped",
            "success",
            "skipped",
            "push",
            "refs/heads/develop",
            True,
        ),
        (
            "FULL",
            "FULL",
            "",
            "false",
            "skipped",
            "skipped",
            "skipped",
            "push",
            "refs/heads/develop",
            False,
        ),
        (
            "FULL",
            "FULL",
            "",
            "true",
            "skipped",
            "skipped",
            "skipped",
            "pull_request",
            "refs/pull/1/merge",
            False,
        ),
        (
            "FULL",
            "FULL",
            "",
            "true",
            "skipped",
            "skipped",
            "skipped",
            "workflow_dispatch",
            "refs/heads/develop",
            False,
        ),
        (
            "FULL",
            "FULL",
            "",
            "true",
            "skipped",
            "skipped",
            "skipped",
            "push",
            "refs/heads/feature/research-synthetic",
            False,
        ),
        (
            "FULL",
            "ACTIVE",
            "full",
            "false",
            "success",
            "skipped",
            "success",
            "push",
            "refs/heads/feature/research-synthetic",
            True,
        ),
        (
            "FULL",
            "ACTIVE",
            "robinhood",
            "false",
            "success",
            "skipped",
            "success",
            "push",
            "refs/heads/feature/robinhood-synthetic",
            True,
        ),
        (
            "FULL",
            "ACTIVE",
            "full",
            "false",
            "success",
            "skipped",
            "skipped",
            "push",
            "refs/heads/feature/research-synthetic",
            False,
        ),
        (
            "FULL",
            "ACTIVE",
            "",
            "false",
            "success",
            "success",
            "skipped",
            "push",
            "refs/heads/feature/research-synthetic",
            True,
        ),
        (
            "FULL",
            "ACTIVE",
            "full",
            "true",
            "skipped",
            "skipped",
            "skipped",
            "push",
            "refs/heads/develop",
            False,
        ),
        (
            "DOCS_ONLY",
            "FULL",
            "",
            "false",
            "skipped",
            "skipped",
            "skipped",
            "push",
            "refs/heads/develop",
            True,
        ),
        (
            "DOCS_ONLY",
            "FULL",
            "",
            "false",
            "skipped",
            "skipped",
            "skipped",
            "pull_request",
            "refs/pull/1/merge",
            True,
        ),
        (
            "FULL",
            "FULL",
            "",
            "false",
            "skipped",
            "success",
            "skipped",
            "pull_request",
            "refs/pull/1/merge",
            True,
        ),
        (
            "FULL",
            "FULL",
            "",
            "",
            "skipped",
            "success",
            "skipped",
            "push",
            "refs/heads/develop",
            True,
        ),
    ],
)
def test_r3m_terminal_aggregator_executes_exact_route_policy(
    mode,
    route,
    profile,
    reuse,
    active,
    broad,
    canonical,
    event,
    ref,
    passed,
):
    import os
    import shutil
    import textwrap

    if os.name == "nt":
        bash = str(Path(shutil.which("git")).resolve().parents[1] / "bin/bash.exe")
    else:
        bash = shutil.which("bash")
    assert bash, "Bash is required to verify the actual source-gates script"
    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    script = textwrap.dedent(
        workflow.split("  source-gates:\n", 1)[1].split("        run: |\n", 1)[1]
    )
    env = {
        **os.environ,
        "STATIC_RESULT": "success",
        "MODE": mode,
        "ROUTE": route,
        "CERT_PROFILE": profile,
        "REUSE": reuse,
        "ACTIVE_RESULT": active,
        "FULL_RESULT": broad,
        "CERT_RESULT": "skipped" if profile == "full" else canonical,
        "FULL_CERT_RESULT": canonical if profile == "full" else "skipped",
        "EVENT": event,
        "REF": ref,
    }
    result = subprocess.run(
        (bash, "-c", script), env=env, capture_output=True, text=True
    )
    assert (result.returncode == 0) is passed, result.stderr
    env["STATIC_RESULT"] = "failure"
    assert (
        subprocess.run((bash, "-c", script), env=env, capture_output=True).returncode
        != 0
    )


def test_r3m_metadata_client_is_read_only_and_lookup_failures_fall_back(monkeypatch):
    def run(argv, **kwargs):
        assert argv == ("gh", "api", "--hostname", "github.com", "repos/synthetic")
        assert kwargs == dict(capture_output=True, text=True, timeout=30, check=True)
        return subprocess.CompletedProcess(argv, 0, '{"id": 123}', "")

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner._github_ci_metadata("repos/synthetic") == {"id": 123}


def test_r3m_c1_preserves_initial_maps_and_rejects_wrong_successors(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch132_r3m_c1_authority_check(root) == ()
    assert runner._arch132_r3m_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH132_R3M_C1_AST_PREDECESSORS, runner.ARCH132_R3M_C1_AST_PINS),
        (
            False,
            runner.ARCH132_R3M_C1_BLOB_PREDECESSORS,
            runner.ARCH132_R3M_C1_BLOB_PINS,
        ),
    ):
        for key, pin in before.items():
            assert runner._arch132_r3m_c1_pin(key, pin, ast_pin=ast_pin) == after[key]
            with pytest.raises(ValueError, match="R3M C1 wrong exact predecessor"):
                runner._arch132_r3m_c1_pin(key, "0" * len(pin), ast_pin=ast_pin)
    monkeypatch.setattr(runner, "ARCH132_R3M_C1_AST_PINS", {})
    assert runner._arch132_r3m_c1_authority_check(root)


def test_r3n_c4_additive_authority_and_exact_predecessors(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch132_r3n_c4_authority_check(root) == ()
    assert runner._arch132_r3n_c3_authority_check(root) == ()
    assert runner._arch132_r3m_authority_check(root) == ()
    for ast_pin, before, after in (
        (True, runner.ARCH132_R3N_C4_AST_PREDECESSORS, runner.ARCH132_R3N_C4_AST_PINS),
        (
            False,
            runner.ARCH132_R3N_C4_BLOB_PREDECESSORS,
            runner.ARCH132_R3N_C4_BLOB_PINS,
        ),
    ):
        for key, pin in before.items():
            expected = (
                after[key]
                if ast_pin
                else runner.READONLY_BLOB_AFTER.get(
                    key, runner.DEPLOYMENT_CANDIDATE_BLOB_PINS.get(key, after[key])
                )
            )
            assert runner._arch132_r3n_c4_pin(key, pin, ast_pin=ast_pin) == expected
            with pytest.raises(ValueError, match="C4 wrong exact predecessor"):
                runner._arch132_r3n_c4_pin(key, "0" * len(pin), ast_pin=ast_pin)
    monkeypatch.setattr(runner, "ARCH132_R3N_C4_AST_PINS", {})
    assert runner._arch132_r3m_authority_check(root)


def test_r3n_c4_skipped_name_drift_fails_authority(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(
        runner, "REVIEWED_SKIPPED_CERTIFICATION_JOB", "certification-tests ( / )"
    )
    assert runner._arch132_r3m_authority_check(root)


def test_r3n_c4_shared_blob_routes_preserve_predecessor_semantics(monkeypatch):
    relative = "docs/AI_TRADING_BOT_HANDOFF.md"
    predecessor = runner.ARCH132_R3N_C4_BLOB_PREDECESSORS[relative]
    expected = runner.ARCH132_R3N_C4_BLOB_PINS[relative]
    assert runner._arch146a_shared_blob_pin(relative, predecessor) == expected
    # Mutable current documents deliberately have no historical D1S3 pin.
    assert runner._arch134_d1s3_shared_successor_pin(relative) is None

    relative = "tests/runtime/checkpoint_runner/test_ci.py"
    assert (
        runner._arch134_d1s3_shared_successor_pin(relative)
        == runner.READONLY_BLOB_AFTER[relative]
    )
    monkeypatch.setattr(
        runner, "_ARCH134_D1S3_SHARED_SUCCESSOR_PIN_PRE_C1", lambda _: None
    )
    assert runner._arch134_d1s3_shared_successor_pin(relative) is None


def test_historical_test_successors_do_not_claim_current_harness_bytes(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    from scripts import source_authority

    relative = "tests/strategies/test_production_strategy_contract.py"
    pin = runner.ARCH132_R3M_C3_BLOB_PINS[relative]
    assert (
        source_authority.classify_path(relative)
        is source_authority.PinClass.CURRENT_MUTABLE
    )
    assert source_authority.blob_matches(root, root / relative, pin)


@pytest.mark.parametrize(
    "paths,expected",
    [
        (("docs/example.md", "docs/a file.md"), "DOCS_ONLY"),
        (("docs/example.md", "src/example.py"), "FULL"),
        (("src/example.py",), "FULL"),
        ((" docs/example.md",), "FULL"),
        (("docs/../src/example.py",), "FULL"),
        (("docs/example.md", "src/deleted.py"), "FULL"),
    ],
)
def test_local_admission_uses_exact_live_range_and_closed_classifier(
    monkeypatch, paths, expected
):
    root, context = _r3n_admission_fixture(monkeypatch)
    context["changed"] = paths
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", "must-not-be-read")
    source = runner._prepublication_source(root)
    assert source.failures == ()
    assert source.mode == expected
    assert source.changed_paths == paths
    assert source.base_head == "b" * 40 and source.base_tree == "c" * 40
    assert source.candidate["head"] == "a" * 40


@pytest.mark.parametrize("unknown", ["UNKNOWN", "", None, [], {"mode": "DOCS_ONLY"}])
def test_general_admission_rejects_unknown_classifier_values(monkeypatch, unknown):
    root, context = _r3n_admission_fixture(monkeypatch)
    context["changed"] = ("docs/example.md",)
    monkeypatch.setattr(runner, "classify_changed_paths", lambda _: unknown)
    assert (
        "R3N changed-path classification drift"
        in runner._arch132_r3n_admission_authority_check(root)
    )


@pytest.mark.parametrize("raw", [b"docs/example.md", b"docs/\xff.md\0"])
def test_local_admission_rejects_incomplete_or_invalid_path_bytes(monkeypatch, raw):
    root, context = _r3n_admission_fixture(monkeypatch)
    context["raw_changed"] = raw
    source = runner._prepublication_source(root)
    assert source.mode is None and source.failures


def _docs_admission_execution_fixture(monkeypatch):
    from scripts.current_source_authority import AuthorityResult

    from scripts import run_test_certification as certification

    root, context = _r3n_admission_fixture(monkeypatch)
    context["changed"] = ("docs/example.md", "docs/nested/a file.md")
    contexts = []
    steps = []

    def forbidden(*args, **kwargs):
        pytest.fail(
            "docs-only invoked tests/static checks, canonical or host/effect dispatch"
        )

    for name in (
        "verify_checkpoint",
        "build_verification_steps",
        "_source_pytest_basetemp",
        "preflight_checkpoint",
        "execute_checkpoint",
    ):
        monkeypatch.setattr(runner, name, forbidden)
    monkeypatch.setattr(certification, "main", forbidden)

    def execute(step, **kwargs):
        assert step.name == "git_range_diff_check"
        assert step.argv == ("git", "diff", "--check", "b" * 40, "a" * 40, "--")
        steps.append(step)
        return replace(
            _outcome(step.name, context.get("range_exit", 0)), argv=step.argv
        )

    def evaluate(repo, *, publication_context):
        assert repo == root
        contexts.append(publication_context)
        return AuthorityResult(
            publication_context,
            "a" * 40,
            "c" * 40,
            ("current",),
            ("bounded authority rejection",)
            if context.get("red") == publication_context
            else (),
        )

    monkeypatch.setattr(runner, "_execute_step", execute)
    monkeypatch.setattr(runner, "evaluate_source_authority", evaluate)
    return root, context, contexts, steps


@pytest.mark.parametrize("red", [None, *runner.PublicationContext])
def test_docs_only_public_admission_requires_both_authorities_without_python_work(
    monkeypatch, tmp_path, capsys, red
):
    root, context, contexts, steps = _docs_admission_execution_fixture(monkeypatch)
    context["red"] = red
    passed, path = runner.prepublication_admission(
        repo_root=root, evidence_root=tmp_path / "evidence"
    )
    assert passed is (red is None)
    assert contexts == list(runner.PublicationContext)
    assert len(steps) == 1
    report = json.loads(path.read_text())
    assert report["mode"] == "DOCS_ONLY"
    assert report["base"] == {"head": "b" * 40, "tree": "c" * 40}
    assert report["changed_paths"] == list(context["changed"])
    assert report["started_from"] == report["finished_at"]
    assert report["started_from"]["head"] == "a" * 40
    assert report["identity_stable"] is True
    assert report["executed_tests"] == []
    assert [command["argv"] for command in report["commands"]] == [list(steps[0].argv)]
    for name in (
        "ruff_check",
        "ruff_format",
        "canonical_certification",
        "host_diagnostics",
        "production_effects",
        "protected_effects",
        "scheduler_mutation",
        "provider_effects",
        "broker_live_effects",
    ):
        assert report[name] == "NOT_RUN"
    for publication_context in runner.PublicationContext:
        status = "FAIL" if red == publication_context else "PASS"
        assert (
            report["authority_contexts"][publication_context.value]["status"] == status
        )
    output = capsys.readouterr().out
    assert "FEATURE_AUTHORITY=" in output and "PROSPECTIVE_DEVELOP_AUTHORITY=" in output
    assert report["status"] == ("PASS" if red is None else "FAIL")


@pytest.mark.parametrize(
    "failure", ["range", "branch", "tree", "dirty", "live_base", "authority_source"]
)
def test_docs_only_admission_rejects_range_and_identity_drift(
    monkeypatch, tmp_path, failure
):
    root, context, contexts, steps = _docs_admission_execution_fixture(monkeypatch)
    execute = runner._execute_step

    def changed(step, **kwargs):
        result = execute(step, **kwargs)
        if failure == "range":
            return replace(result, exit_code=1)
        if failure == "branch":
            context["branch"] = "feature/test-suite-another"
        elif failure == "dirty":
            context["porcelain"] = " M docs/example.md"
        elif failure == "live_base":
            context["remote_head"] = "d" * 40
        elif failure == "tree":
            before = runner._git_state(root)
            monkeypatch.setattr(
                runner, "_git_state", lambda _: {**before, "tree": "d" * 40}
            )
        elif failure == "authority_source":
            evaluate = runner.evaluate_source_authority
            monkeypatch.setattr(
                runner,
                "evaluate_source_authority",
                lambda *a, **k: replace(evaluate(*a, **k), head="d" * 40),
            )
        return result

    monkeypatch.setattr(runner, "_execute_step", changed)
    passed, path = runner.prepublication_admission(
        repo_root=root, evidence_root=tmp_path / "evidence"
    )
    report = json.loads(path.read_text())
    assert not passed and report["status"] == "FAIL"
    if failure == "range":
        assert contexts == []
    elif failure != "authority_source":
        assert report["identity_stable"] is False
    assert len(steps) == 1 and report["executed_tests"] == []


@pytest.mark.parametrize(
    "paths", [("src/example.py",), ("docs/example.md", "src/example.py")]
)
def test_full_public_admission_retains_ordinary_complete_verifier(
    monkeypatch, tmp_path, paths
):
    root, context = _r3n_admission_fixture(monkeypatch)
    context["changed"] = paths
    captured = []

    def verify(spec, **kwargs):
        captured.append(spec)
        version = kwargs.pop("ruff_version")
        assert version["expected"] == version["actual"] == "ruff 0.17.3"
        assert version["exit_code"] == 0
        assert kwargs == {"repo_root": root, "evidence_root": tmp_path}
        assert spec.tests == runner.ARCH132_R3N_ADMISSION_TESTS
        assert spec.ruff_paths == (".",)
        assert (
            spec.authority_check is runner._arch134_r3n_prepublication_authority_check
        )
        return True, tmp_path / "report.json"

    monkeypatch.setattr(runner, "verify_checkpoint", verify)
    monkeypatch.setattr(
        runner,
        "_docs_only_prepublication_admission",
        lambda **_: pytest.fail("FULL took docs-only route"),
    )
    assert runner.prepublication_admission(repo_root=root, evidence_root=tmp_path) == (
        True,
        tmp_path / "report.json",
    )
    assert len(captured) == 1


def test_full_admission_executes_combined_checks_both_authorities_and_test_bundle(
    monkeypatch, tmp_path
):
    from scripts.current_source_authority import AuthorityResult

    root, _ = _r3n_admission_fixture(monkeypatch)
    contexts = []
    commands = []

    def evaluate(repo, *, publication_context, checkpoints=None):
        if checkpoints is not None:
            assert len(checkpoints) == 1
            failures = checkpoints[0].authority_check(repo)
        else:
            contexts.append(publication_context)
            failures = ()
        return AuthorityResult(
            publication_context, "a" * 40, "c" * 40, ("current",), failures
        )

    def execute(step, **kwargs):
        commands.append(step)
        return replace(_outcome(step.name, 0), argv=step.argv)

    monkeypatch.setattr(runner, "evaluate_source_authority", evaluate)
    monkeypatch.setattr(runner, "_execute_step", execute)
    monkeypatch.setattr(runner, "_source_pytest_basetemp", lambda: tmp_path / "pytest")
    passed, path = runner.prepublication_admission(
        repo_root=root, evidence_root=tmp_path / "evidence"
    )
    assert passed
    assert [step.name for step in commands] == [
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
    ]
    assert contexts == list(runner.PublicationContext)
    report = json.loads(path.read_text())
    assert report["mode"] == "FULL"
    assert report["executed_tests"] == list(
        runner._prepublication_admission_tests(("scripts/checkpoint_runner.py",))
    )
    assert report["authority_checked"] and report["identity_stable"]


def test_docs_only_admission_real_git_range_never_launches_python(
    monkeypatch, tmp_path
):
    from scripts.current_source_authority import AuthorityResult

    from scripts import run_test_certification as certification

    root = tmp_path / "source"
    root.mkdir()

    def git(*args):
        return subprocess.run(
            ("git", *args), cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Admission Test")
    git("config", "user.email", "admission@example.invalid")
    git("remote", "add", "origin", "https://github.com/callmedraken/ai-trading-bot.git")
    (root / "docs").mkdir()
    doc = root / "docs/example.md"
    doc.write_text("base\n")
    git("add", "--", "docs/example.md")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    base_tree = git("rev-parse", "HEAD^{tree}")
    git("checkout", "-b", "feature/test-suite-docs-regression")
    doc.write_text("candidate\n")
    git("add", "--", "docs/example.md")
    git("commit", "-m", "docs")
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    monkeypatch.setattr(runner, "_REPOSITORY_ROOT", root)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda repo, branch: base)
    monkeypatch.setattr(
        runner,
        "_arch132_r3n_admission_authority_check",
        lambda repo: runner._prepublication_source(repo).failures,
    )
    contexts = []

    def evaluate(repo, *, publication_context):
        contexts.append(publication_context)
        return AuthorityResult(publication_context, head, tree, ("current",), ())

    monkeypatch.setattr(runner, "evaluate_source_authority", evaluate)

    def forbidden(*a, **k):
        pytest.fail("docs-only attempted Python verification or protected dispatch")

    for name in (
        "verify_checkpoint",
        "build_verification_steps",
        "_source_pytest_basetemp",
        "preflight_checkpoint",
        "execute_checkpoint",
    ):
        monkeypatch.setattr(runner, name, forbidden)
    monkeypatch.setattr(certification, "main", forbidden)
    original_run = runner.subprocess.run
    calls = []

    def read_only(argv, **kwargs):
        assert argv[0] == "git" and argv[1] in {
            "rev-parse",
            "status",
            "remote",
            "merge-base",
            "diff",
        }
        if argv[1] == "remote":
            assert tuple(argv[2:]) == ("get-url", "origin")
        calls.append(tuple(argv))
        return original_run(argv, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", read_only)
    passed, path = runner.prepublication_admission(
        repo_root=root, evidence_root=tmp_path / "evidence"
    )
    report = json.loads(path.read_text())
    assert passed and report["identity_stable"]
    assert report["base"] == {"head": base, "tree": base_tree}
    assert (
        report["started_from"]["head"] == head
        and report["started_from"]["tree"] == tree
    )
    assert report["changed_paths"] == ["docs/example.md"]
    assert report["executed_tests"] == [] and contexts == list(
        runner.PublicationContext
    )
    assert ("git", "diff", "--check", base, head, "--") in calls


@pytest.mark.parametrize("failure", ["empty", "unknown", "origin"])
def test_public_admission_does_not_retry_rejected_source_as_full(
    monkeypatch, tmp_path, failure
):
    root, context = _r3n_admission_fixture(monkeypatch)
    if failure == "empty":
        context["changed"] = ()
    elif failure == "unknown":
        monkeypatch.setattr(runner, "classify_changed_paths", lambda _: "UNKNOWN")
    else:
        context["origin"] = "https://github.com/other/repository.git"
    monkeypatch.setattr(
        runner,
        "verify_checkpoint",
        lambda *a, **k: pytest.fail("rejected source retried as FULL"),
    )
    with pytest.raises(RuntimeError, match="general admission source rejected"):
        runner.prepublication_admission(
            repo_root=root, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("actual", ["ruff 0.15.21", "unavailable", "ruff 0.17.30"])
def test_full_admission_rejects_ruff_mismatch_before_verification(
    monkeypatch, tmp_path, actual
):
    root, _ = _r3n_admission_fixture(monkeypatch)
    monkeypatch.setattr(
        runner,
        "check_ruff_version",
        lambda *args: {"exit_code": 1, "expected": "ruff 0.17.3", "actual": actual},
    )
    monkeypatch.setattr(
        runner,
        "verify_checkpoint",
        lambda *args, **kwargs: pytest.fail("expensive gate started"),
    )
    with pytest.raises(RuntimeError, match=f"expected ruff 0.17.3; current {actual}"):
        runner.prepublication_admission(repo_root=root, evidence_root=tmp_path)


def _distributed_reuse_fixture():
    from copy import deepcopy

    args, responses, run, jobs, runs_path, jobs_path = _reuse_fixture()
    canonical = jobs[2]
    lanes = []
    for index in range(1, 8):
        job = deepcopy(canonical)
        job["id"] = 1000 + index
        job["name"] = f"certification-full (broad-{index})"
        lanes.append(job)
    canonical["conclusion"] = "skipped"
    canonical["steps"] = []
    jobs.extend(lanes)
    responses[jobs_path]["total_count"] = len(jobs)
    return args, responses, run, jobs, runs_path, jobs_path


def test_current_full_reuse_retains_all_seven_original_jobs():
    args, _, _, jobs, _, _ = _distributed_reuse_fixture()
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["jobs"] == jobs
    assert result["full_lane_jobs"] == [
        f"certification-full (broad-{i})" for i in range(1, 8)
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "malformed",
        "extra",
        "failure",
        "timeout",
        "over_budget",
        "missing_hygiene",
        "missing_functional",
        "attempt_two",
        "job_attempt",
        "job_sha",
        "job_run",
        "route_executed",
        "wrong_profile",
        "duplicate_id",
        "missing_id",
        "static_failed",
        "active_failed",
        "gate_failed",
        "truncated",
        "tree",
        "branch",
        "event",
    ],
)
def test_current_full_reuse_rejects_incomplete_or_ambiguous_evidence(mutation):
    from copy import deepcopy

    args, responses, run, jobs, runs_path, jobs_path = _distributed_reuse_fixture()
    lane = jobs[-1]
    if mutation == "missing":
        jobs.pop()
    elif mutation == "duplicate":
        jobs.append(deepcopy(lane))
    elif mutation == "malformed":
        lane["name"] = "certification-full (broad-07)"
    elif mutation == "extra":
        extra = deepcopy(lane)
        extra["name"] = "certification-full (broad-8)"
        jobs.append(extra)
    elif mutation in ("failure", "timeout"):
        lane["conclusion"] = "failure" if mutation == "failure" else "timed_out"
    elif mutation == "over_budget":
        lane["steps"][-1]["conclusion"] = "failure"
    elif mutation in ("missing_hygiene", "missing_functional"):
        lane["steps"].pop(-1 if mutation == "missing_hygiene" else 0)
    elif mutation == "attempt_two":
        run["run_attempt"] = responses[
            "repos/callmedraken/ai-trading-bot/actions/runs/100"
        ]["run_attempt"] = 2
    elif mutation in ("job_attempt", "job_sha", "job_run"):
        lane[
            {"job_attempt": "run_attempt", "job_sha": "head_sha", "job_run": "run_id"}[
                mutation
            ]
        ] = 2
    elif mutation == "route_executed":
        jobs[2]["conclusion"] = "success"
    elif mutation == "wrong_profile":
        jobs[2]["name"] = jobs[2]["name"].replace(" / full)", " / robinhood)")
    elif mutation in ("static_failed", "active_failed", "gate_failed"):
        jobs[{"static_failed": 0, "active_failed": 1, "gate_failed": 4}[mutation]][
            "conclusion"
        ] = "failure"
    elif mutation == "tree":
        responses[f"repos/callmedraken/ai-trading-bot/git/commits/{args['head']}"][
            "tree"
        ]["sha"] = "c" * 40
    elif mutation == "branch":
        run["head_branch"] = "feature/research-unknown"
    elif mutation == "event":
        run["event"] = "workflow_dispatch"
    elif mutation == "duplicate_id":
        lane["id"] = jobs[-2]["id"]
    elif mutation == "missing_id":
        del lane["id"]
    responses[jobs_path]["total_count"] = 101 if mutation == "truncated" else len(jobs)
    assert (
        runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is False
    )


def test_current_full_reuse_rejects_old_shared_runner_topology():
    args, *_ = _reuse_fixture()
    assert (
        runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is False
    )


def test_current_full_reuse_accepts_exact_literal_skipped_job_name():
    args, _, _, jobs, _, _ = _distributed_reuse_fixture()
    jobs[2]["name"] = runner.REVIEWED_SKIPPED_CERTIFICATION_JOB
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["jobs"] == jobs


def test_current_distributed_full_workflow_is_exact_and_isolated():
    from scripts.distributed_full import (
        FULL_DETACHED_BRANCH_BOOTSTRAP,
        predecessor_workflow,
    )

    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert runner._arch134_current_batch_workflow_is_reviewed(workflow)
    matrix = workflow.split("  certification-full:\n", 1)[1].split(
        "  source-gates:\n", 1
    )[0]
    assert "    needs: source-static\n" in matrix
    assert "    runs-on: windows-latest\n" in matrix
    assert "      fail-fast: false\n" in matrix
    assert "        lane: [1, 2, 3, 4, 5, 6, 7]\n" in matrix
    assert "          ref: ${{ github.sha }}" in matrix
    assert (
        "".join(
            "          " + line + "\n"
            for line in FULL_DETACHED_BRANCH_BOOTSTRAP.splitlines()
        )
        in matrix
    )
    assert "([string](git branch --show-current)).Trim()" not in matrix
    assert "              --lane $env:FULL_LANE `" in matrix
    artifact = "canonical-certification-full-broad-${{ matrix.lane }}"
    assert matrix.count("name: " + artifact) == 1
    assert (
        len({artifact.replace("${{ matrix.lane }}", str(i)) for i in range(1, 8)}) == 7
    )
    predecessor = predecessor_workflow(workflow)
    assert "certification-full" not in predecessor
    assert not runner._arch134_current_batch_workflow_is_reviewed(predecessor)


def test_p4_workflow_projection_preserves_historical_owner_and_fails_closed():
    root = Path(runner.__file__).resolve().parents[1]
    workflow_path = root / ".github/workflows/checkpoint-source-gates.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    functions = {
        node.name: node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
    }
    names = (
        "_arch134_current_batch_workflow_is_reviewed",
        "_arch134_readonly_diagnostic_batch_workflow_successor",
    )
    for name in names:
        expected = runner.ARCH134_READONLY_DIAGNOSTIC_NEW_AST_PINS[name]
        assert ownership.current_owner(name) == "checkpoint_runner"
        assert ownership.classify_path(name) is ownership.PinClass.CURRENT_MUTABLE
        assert ownership.ast_matches(root, name, functions[name], expected)

    p4_row = "              " + runner.ARCH147_P4_NAME + " `\n"
    assert workflow.count(p4_row) == 1
    predicates = (
        runner._arch134_current_batch_workflow_is_reviewed,
        runner._batch_workflow_is_reviewed,
    )
    for predicate in predicates:
        assert predicate(workflow)
        assert not predicate(workflow.replace(p4_row, "", 1))
        assert not predicate(workflow.replace(p4_row, p4_row + p4_row, 1))
        assert not predicate(
            workflow.replace(
                p4_row,
                "              " + runner.ARCH147_P4_NAME + "\n",
                1,
            )
        )


def test_p4_gui_dependency_is_installed_in_supported_execution_jobs():
    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )

    def job_section(name: str) -> str:
        start_marker = f"  {name}:\n"
        start = workflow.index(start_marker)
        remainder = workflow[start + len(start_marker) :]
        next_job = re.search(r"\n  [a-z][a-z0-9-]*:\n", remainder)
        if next_job is None:
            return workflow[start:]
        return workflow[start : start + len(start_marker) + next_job.start()]

    def installed_packages(section: str) -> set[str]:
        packages: set[str] = set()
        for match in re.finditer(
            r"(?ms)^\s*python -m pip install --disable-pip-version-check `\n"
            r"(?P<arguments>(?:\s+\"[^\"]+\"(?: `)?\n)+)",
            section,
        ):
            packages.update(re.findall(r"\"([^\"]+)\"", match.group("arguments")))
        return packages

    gui_jobs = (
        "active-tests",
        "full-tests",
        "certification-tests",
        "certification-full",
    )
    for job in gui_jobs:
        assert "PySide6>=6.10.1,<6.11" in installed_packages(job_section(job))

    assert "PySide6>=6.10.1,<6.11" not in installed_packages(
        job_section("source-static")
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("lane: [1, 2, 3, 4, 5, 6, 7]", "lane: [1, 2, 3, 4, 5, 6, 6]"),
        ("fail-fast: false", "fail-fast: true"),
        ("--lane $env:FULL_LANE", "--lane 1"),
        ("--ci-source-static", "--plan"),
        ("ref: ${{ github.sha }}", "ref: ${{ github.ref_name }}"),
        (
            "$CurrentBranchLines = @(git branch --show-current)",
            "$CurrentBranchLines = git branch --show-current",
        ),
        (
            "if ($CurrentBranchLines.Count -eq 0)",
            "if ($CurrentBranchLines.Count -eq 1)",
        ),
        (
            "elseif ($CurrentBranchLines.Count -eq 1)",
            "elseif ($CurrentBranchLines.Count -ge 1)",
        ),
        ("throw 'Ambiguous certification checkout branch output'", "# accept"),
        ("throw 'Failed to inspect certification checkout branch'", "# accept"),
        ("if ($CurrentBranch -ne '')", "if ($false)"),
        (
            "name: canonical-certification-full-broad-${{ matrix.lane }}",
            "name: canonical-certification-full",
        ),
        (
            "SOURCE_STATIC_RESULT: ${{ needs.source-static.result }}",
            "SOURCE_STATIC_RESULT: success",
        ),
        ('test "$FULL_CERT_RESULT" = "success"', "true"),
    ],
)
def test_current_distributed_workflow_mutations_fail_closed(old, new):
    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert old in workflow
    assert not runner._arch134_current_batch_workflow_is_reviewed(
        workflow.replace(old, new)
    )


@pytest.mark.parametrize(
    "matrix_result,passed",
    [
        ("success", True),
        ("failure", False),
        ("cancelled", False),
        ("timed_out", False),
        ("skipped", False),
    ],
)
def test_actual_full_aggregate_requires_every_matrix_lane(matrix_result, passed):
    import os
    import shutil
    import textwrap

    root = Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    script = textwrap.dedent(
        workflow.split("  source-gates:\n", 1)[1].split("        run: |\n", 1)[1]
    )
    bash = (
        str(Path(shutil.which("git")).resolve().parents[1] / "bin/bash.exe")
        if os.name == "nt"
        else shutil.which("bash")
    )
    env = {
        **os.environ,
        "STATIC_RESULT": "success",
        "MODE": "FULL",
        "ROUTE": "ACTIVE",
        "CERT_PROFILE": "full",
        "REUSE": "false",
        "ACTIVE_RESULT": "success",
        "FULL_RESULT": "skipped",
        "CERT_RESULT": "skipped",
        "FULL_CERT_RESULT": matrix_result,
        "EVENT": "push",
        "REF": "refs/heads/feature/research-example",
    }
    result = subprocess.run(
        (bash, "-c", script), env=env, capture_output=True, text=True
    )
    assert (result.returncode == 0) == passed, result.stderr


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows PowerShell 5.1")
def test_full_detached_bootstrap_native_empty_stdout(tmp_path):
    from scripts.distributed_full import FULL_DETACHED_BRANCH_BOOTSTRAP

    powershell = shutil.which("powershell.exe")
    assert powershell is not None, "Windows admission requires powershell.exe"
    git = shutil.which("git")
    assert git is not None, "Windows admission requires real Git"
    repo = tmp_path / "repo"
    repo.mkdir()
    # Discard ambient repository selectors so both the real temporary repository
    # and the intentional non-repository failure exercise their own cwd.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def run_git(*args):
        return subprocess.run(
            (git, *args),
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()

    run_git("init")
    run_git("config", "user.name", "Native bootstrap regression")
    run_git("config", "user.email", "native-bootstrap@example.invalid")
    run_git("config", "commit.gpgsign", "false")
    (repo / "tracked.txt").write_text("native regression\n", encoding="utf-8")
    run_git("add", "--", "tracked.txt")
    run_git("commit", "-m", "native regression")
    head = run_git("rev-parse", "HEAD")
    branch = run_git("branch", "--show-current")
    assert branch

    script = tmp_path / "bootstrap.ps1"
    script.write_text(
        "Set-StrictMode -Version Latest\n$ErrorActionPreference = 'Stop'\n"
        "if ($PSVersionTable.PSVersion.Major -ne 5) {\n"
        "    throw 'Expected Windows PowerShell 5.1'\n}\n"
        + FULL_DETACHED_BRANCH_BOOTSTRAP
        + "if ($CurrentBranch -cne '') { throw 'Expected exact empty identity' }\n"
        + "if ($CurrentBranchLines.Count -ne 0) {\n"
        + "    throw 'Expected zero native lines'\n}\n"
        + "Write-Output 'DETACHED_NATIVE_EMPTY_PASS'\n",
        encoding="utf-8",
    )

    def run_ps(cwd, path=script):
        return subprocess.run(
            (powershell, "-NoProfile", "-NonInteractive", "-File", str(path)),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    attached = run_ps(repo)
    assert attached.returncode != 0
    assert f"Certification branch mismatch: {branch}" in attached.stderr
    assert "DETACHED_NATIVE_EMPTY_PASS" not in attached.stdout

    run_git("checkout", "--detach", head)
    assert run_git("rev-parse", "HEAD") == head
    assert run_git("branch", "--show-current") == ""
    legacy = tmp_path / "legacy.ps1"
    legacy.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "$CurrentBranch = ([string](git branch --show-current)).Trim()\n",
        encoding="utf-8",
    )
    failed_legacy = run_ps(repo, legacy)
    assert failed_legacy.returncode != 0
    assert "null-valued expression" in failed_legacy.stderr

    detached = run_ps(repo)
    assert detached.returncode == 0, detached.stderr
    assert detached.stdout.strip() == "DETACHED_NATIVE_EMPTY_PASS"

    # Real native Git failure: the cwd is outside any repository, not a fake
    # executable, a supplied $null, or a substituted native command.
    outside = tmp_path / "not-a-repository"
    outside.mkdir()
    failed = run_ps(outside)
    assert failed.returncode != 0
    assert "Failed to inspect certification checkout branch" in failed.stderr
    assert "DETACHED_NATIVE_EMPTY_PASS" not in failed.stdout


def _current_canonical_attempt_fixture(profile, attempt):
    fixture = (
        _distributed_reuse_fixture() if profile == "full" else _reuse_fixture(profile)
    )
    args, responses, run, jobs, runs_path, jobs_path = fixture
    if profile == "robinhood":
        jobs.append(
            {
                "name": "certification-full (broad-" + "$" + "{{ matrix.lane }})",
                "status": "completed",
                "conclusion": "skipped",
                "steps": [],
                "run_id": run["id"],
                "head_sha": args["head"],
                "run_attempt": attempt,
            }
        )
    run["run_attempt"] = attempt
    responses["repos/callmedraken/ai-trading-bot/actions/runs/100"]["run_attempt"] = (
        attempt
    )
    for job in jobs:
        job["run_attempt"] = attempt
        # Carried jobs keep original timestamps in the current-attempt view.
        job["started_at"] = "2026-10-28T01:00:00Z"
        job["completed_at"] = "2026-10-28T01:01:00Z"
    page = responses.pop(jobs_path)
    jobs_path = jobs_path.replace("/attempts/1/", f"/attempts/{attempt}/")
    page["total_count"] = len(jobs)
    responses[jobs_path] = page
    return args, responses, run, jobs, runs_path, jobs_path


@pytest.mark.parametrize("profile", ["full", "robinhood"])
@pytest.mark.parametrize("attempt", [1, 2])
def test_current_canonical_reuse_accepts_original_or_one_reviewed_retry(
    profile, attempt
):
    from copy import deepcopy

    args, responses, run, jobs, _, _ = _current_canonical_attempt_fixture(
        profile, attempt
    )
    preserved = deepcopy(responses)
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["run_attempt"] == attempt and result["run"] == run
    assert result["jobs"] == jobs
    assert all(job["run_attempt"] == attempt for job in result["jobs"])
    assert responses == preserved
    assert all(job["started_at"] == "2026-10-28T01:00:00Z" for job in result["jobs"])


@pytest.mark.parametrize("profile", ["full", "robinhood"])
@pytest.mark.parametrize(
    "mutation",
    [
        "sha",
        "ref",
        "workflow",
        "repository",
        "event",
        "tree",
        "missing_static",
        "failed_static",
        "missing_lane",
        "failed_lane",
        "malformed_lane",
        "duplicate_lane",
        "hygiene",
        "active",
        "gate",
        "job_attempt",
        "detail_attempt",
        "attempt_three",
    ],
)
def test_current_reviewed_retry_rejects_incomplete_or_wrong_provenance(
    profile, mutation
):
    from copy import deepcopy

    args, responses, run, jobs, _, jobs_path = _current_canonical_attempt_fixture(
        profile, 2
    )
    prefix = "repos/callmedraken/ai-trading-bot"
    detail = responses[f"{prefix}/actions/runs/100"]
    lane = next(
        job
        for job in jobs
        if (
            job["name"].startswith("certification-full (broad-")
            if profile == "full"
            else job["name"].startswith("certification-tests (")
        )
    )
    if mutation in {"sha", "ref", "workflow", "event", "repository"}:
        key, value = {
            "sha": ("head_sha", "c" * 40),
            "ref": ("head_branch", "feature/research-wrong"),
            "workflow": ("workflow_id", 999),
            "event": ("event", "workflow_dispatch"),
            "repository": ("repository", {"id": 999, "full_name": "other/repo"}),
        }[mutation]
        run[key] = detail[key] = value
    elif mutation == "tree":
        responses[f"{prefix}/git/commits/{args['head']}"]["tree"]["sha"] = "c" * 40
    elif mutation == "missing_static":
        jobs.remove(next(job for job in jobs if job["name"] == "source-static"))
    elif mutation in {"failed_static", "active", "gate"}:
        name = {
            "failed_static": "source-static",
            "active": "active-tests",
            "gate": "source-gates",
        }[mutation]
        next(job for job in jobs if job["name"] == name)["conclusion"] = "failure"
    elif mutation == "missing_lane":
        jobs.remove(lane)
    elif mutation == "failed_lane":
        lane["conclusion"] = "failure"
    elif mutation == "malformed_lane":
        lane["name"] += " malformed"
    elif mutation == "duplicate_lane":
        jobs.append(deepcopy(lane))
    elif mutation == "hygiene":
        lane["steps"][-1]["conclusion"] = "failure"
    elif mutation == "job_attempt":
        lane["run_attempt"] = 1
    elif mutation == "detail_attempt":
        detail["run_attempt"] = 1
    elif mutation == "attempt_three":
        run["run_attempt"] = detail["run_attempt"] = 3
        for job in jobs:
            job["run_attempt"] = 3
        responses[jobs_path.replace("/attempts/2/", "/attempts/3/")] = responses.pop(
            jobs_path
        )
        jobs_path = jobs_path.replace("/attempts/2/", "/attempts/3/")
    responses[jobs_path]["total_count"] = len(jobs)
    assert (
        runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)[
            "reuse"
        ]
        is False
    )
