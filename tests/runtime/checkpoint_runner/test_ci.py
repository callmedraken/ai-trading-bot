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
        "arch134-f2-five-session-soak-readiness": "robinhood",
        "arch134-f1-five-session-soak": "robinhood",
        "arch134-d1r8-d1-session-execution-consumer": "robinhood",
        "arch134-d1r7-d1-session-authorization": "robinhood",
        "arch134-d1r6-overnight-wake-arming": "robinhood",
        "arch134-d1r5-pre-market-wake-qualification": "robinhood",
        "arch134-alpaca-authentication-qualification": "robinhood",
        "arch134-armed-paper-mvp": "robinhood",
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
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 70
    assert len(set(runner.ACTIVE_CI_CHECKPOINTS)) == 70
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


def test_d1r2_exact_successor_overlay_registration_and_frozen_refs():
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
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 70
    assert runner.ACTIVE_CI_CHECKPOINTS[-6:] == (
        runner.ARCH134_ARMED_PAPER_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME,
        runner.ARCH134_PRODUCTION_PAPER_RUNTIME_NAME,
        runner.ARCH134_RUNTIME_ACL_NAME,
    )
    assert (
        runner.REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
        == "5a9f7a0a069cbcd89b07ca9114f5618e44b0ba07ace5d3bd81fae423e0649515"
    )
    root = Path(runner.__file__).resolve().parents[1]
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
