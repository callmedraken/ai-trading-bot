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
    assert runner.ACTIVE_CI_CHECKPOINTS[4] == name
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
    assert runner.ACTIVE_CI_CHECKPOINTS[6] == name
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
    repo = Path(runner.__file__).resolve().parents[1]
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(old) == 1
    assert not runner._batch_workflow_is_reviewed(workflow.replace(old, new, 1))


def test_ci_certification_profile_mapping_is_explicit_and_bounded():
    assert runner.CI_CERTIFICATION_PROFILES == {
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
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 79
    assert len(set(runner.ACTIVE_CI_CHECKPOINTS)) == 79
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
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 79
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


def test_arch146a_registration_and_additive_successor_authority():
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
    assert runner._arch146a_authority_check(root) == ()
    assert runner._arch134_r5_authority_check(root) == ()
    assert (
        runner._arch146a_predecessor_active_inventory()
        == runner.ACTIVE_CI_CHECKPOINTS[1:]
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
    assert runner._batch_workflow_is_reviewed(workflow)


def test_arch146a_c1_exact_successors_and_frozen_failed_maps():
    root = Path(runner.__file__).resolve().parents[1]
    runner._arch146a_maps()
    runner._arch146a_c1_maps()
    assert runner._arch132_r3n_c1_arch146a_c2_authority_check(root) == ()
    assert runner._arch146a_authority_check(root) == ()
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
    assert runner._arch146a_authority_check(root) == ()
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
        "source-gates": ["Require source gate success"],
    }
    jobs = [
        {
            "name": name,
            "run_id": 100,
            "run_attempt": 1,
            "head_sha": head,
            "status": "completed",
            "conclusion": "success",
            "steps": [
                {"name": step, "status": "completed", "conclusion": "success"}
                for step in steps
            ],
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
        "certification-tests ( / )": (),
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
                if name == "certification-tests ( / )"
                or (name == "active-tests" and not registered)
                else "success"
            ),
            "steps": [
                {"name": step, "status": "completed", "conclusion": "success"}
                for step in step_names
            ],
        }
        for name, step_names in broad_steps.items()
    ]
    responses[jobs_path]["total_count"] = len(jobs)
    return args, responses, run, jobs, runs_path, jobs_path


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
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/scripts/certification_runner/test_lanes.py",
    )


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
        "changed": "scripts/checkpoint_runner.py\n",
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
        "invalid_classification",
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
        context["changed"] = ""
    elif mutation == "malformed_identity":
        context["remote_head"] = "malformed"
    elif mutation == "unavailable_identity":

        def unavailable(_, branch):
            assert branch == "develop"
            raise RuntimeError("remote unavailable")

        monkeypatch.setattr(runner, "_remote_branch_head", unavailable)
    elif mutation == "invalid_classification":
        context["changed"] = "docs/example.md\n"
    else:
        context["authority"] = ("invalid current topology",)
    assert runner._arch132_r3n_admission_authority_check(
        Path(runner.__file__).resolve().parents[1]
    )


@pytest.mark.parametrize("profile", ["full", "robinhood"])
def test_r3m_exact_feature_certification_reused(profile):
    args, _, _, _, _, _ = _reuse_fixture(profile)
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["head"] == args["head"] and result["tree"] == args["tree"]
    assert result["run_id"] == 100 and result["run_attempt"] == 1
    assert result["profile"] == profile


def test_r3n_exact_feature_broad_source_gate_reused():
    args, _, _, _, _, _ = _broad_reuse_fixture()
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is True
    assert result["reason"] == "exact_feature_broad_source_gate"
    assert result["reuse_kind"] == "broad_source_gate"
    assert result["profile"] == ""
    assert result["shards"] == [0, 1, 2, 3]
    assert result["run_attempt"] == 1


def test_r3n_registered_active_broad_source_gate_reused():
    args, _, _, _, _, _ = _broad_reuse_fixture(registered=True)
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_failed_shard_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(job for job in jobs if job["name"] == "full-tests (2)")["conclusion"] = (
        "failure"
    )
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_failed_hygiene_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(job for job in jobs if job["name"] == "full-tests (1)")["steps"][-1][
        "conclusion"
    ] = "failure"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_registered_active_failure_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=True)
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "failure"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_registered_active_skip_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=True)
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "skipped"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


def test_r3n_unregistered_active_run_is_not_reusable():
    args, _, _, jobs, _, _ = _broad_reuse_fixture()
    next(job for job in jobs if job["name"] == "active-tests")["conclusion"] = "success"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
    assert result["reuse"] is False


@pytest.mark.parametrize("route", ["registered", "unregistered"])
def test_r3n_broad_certification_run_is_not_reusable(route):
    args, _, _, jobs, _, _ = _broad_reuse_fixture(registered=route == "registered")
    next(job for job in jobs if job["name"] == "certification-tests ( / )")[
        "conclusion"
    ] = "success"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
            "repos/callmedraken/ai-trading-bot/actions/workflows/checkpoint-source-gates.yml"
        ]["name"] = "Other workflow"
    result = runner.find_reusable_ci_certification(runner._checkpoint_specs(), **args)
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
    args, responses, *_ = _reuse_fixture()
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
        "CERT_RESULT": canonical,
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
