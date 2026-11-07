import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.distributed_full import SKIPPED_FULL_JOB

from scripts import checkpoint_runner as runner
from scripts import develop_reuse_successor as successor

REPOSITORY = "callmedraken/ai-trading-bot"
BASE = "bae1dcd1837e4ffb3a6e6dfc599597869f1f72c4"
CERTIFIED = "235118f70b7c7039055e9fea45ccf27df46671a0"
CERTIFIED_TREE = "972004101036afe52642ed93c38fed21ea479956"
CURRENT = "068bd28036bfe3ab1252f484ad967eb0f9fca8f0"
CURRENT_TREE = "7bf0e3a9c1fd97db981f539510b716d2f212d7c1"
FEATURE = "feature/robinhood-live-prototype-current"
WORKFLOW_ID = 101
FEATURE_RUN = 42358983502
DOCS_RUN = 42359762236
CURRENT_RUN = 42359807677
SECOND_CERTIFIED = "a" * 40
SECOND_TREE = "b" * 40
SECOND_FEATURE_RUN = 42358983501


def _step(name: str, conclusion: str = "success") -> dict:
    return {"name": name, "status": "completed", "conclusion": conclusion}


def _job(
    name: str,
    *,
    head: str,
    run_id: int,
    steps: list[dict] | None = None,
    conclusion: str = "success",
) -> dict:
    return {
        "name": name,
        "id": run_id,
        "run_id": run_id,
        "run_attempt": 1,
        "head_sha": head,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [] if steps is None else steps,
    }


def _run(run_id: int, head: str, branch: str, *, conclusion: str = "success") -> dict:
    repo = {"full_name": REPOSITORY, "id": 7}
    return {
        "id": run_id,
        "run_attempt": 1,
        "repository": repo,
        "head_repository": repo,
        "name": "Checkpoint Source Gates",
        "workflow_id": WORKFLOW_ID,
        "path": ".github/workflows/checkpoint-source-gates.yml",
        "head_sha": head,
        "head_branch": branch,
        "event": "push",
        "status": "completed",
        "conclusion": conclusion,
    }


def _feature_jobs() -> list[dict]:
    jobs = [
        _job(
            "source-static",
            head=CERTIFIED,
            run_id=FEATURE_RUN,
            steps=[
                _step("Resolve source gate route"),
                _step("Verify active checkpoint static authority"),
            ],
        ),
        _job(
            "active-tests",
            head=CERTIFIED,
            run_id=FEATURE_RUN,
            steps=[_step("Verify active checkpoint tests")],
        ),
        _job(
            "certification-tests (arch147-live-prototype / full)",
            head=CERTIFIED,
            run_id=FEATURE_RUN,
            steps=[_step("Run canonical certification profile")],
        ),
    ]
    jobs.extend(
        _job(
            f"certification-full (broad-{index})",
            head=CERTIFIED,
            run_id=FEATURE_RUN,
            steps=[
                _step("Run canonical certification profile"),
                _step("Enforce canonical certification hygiene budget"),
            ],
        )
        for index in range(1, 8)
    )
    jobs.extend(
        [
            _job(
                "full-tests",
                head=CERTIFIED,
                run_id=FEATURE_RUN,
                steps=[],
                conclusion="skipped",
            ),
            _job(
                "source-gates",
                head=CERTIFIED,
                run_id=FEATURE_RUN,
                steps=[_step("Require source gate success")],
            ),
        ]
    )
    return jobs


def _docs_jobs() -> list[dict]:
    jobs = [
        _job(
            "source-static",
            head=CURRENT,
            run_id=DOCS_RUN,
            steps=[_step("Classify changed paths")],
        ),
        _job(
            "source-gates",
            head=CURRENT,
            run_id=DOCS_RUN,
            steps=[_step("Require source gate success")],
        ),
        _job(
            "active-tests",
            head=CURRENT,
            run_id=DOCS_RUN,
            steps=[],
            conclusion="skipped",
        ),
        _job(
            "full-tests", head=CURRENT, run_id=DOCS_RUN, steps=[], conclusion="skipped"
        ),
        _job(
            runner.REVIEWED_SKIPPED_CERTIFICATION_JOB,
            head=CURRENT,
            run_id=DOCS_RUN,
            steps=[],
            conclusion="skipped",
        ),
        _job(
            SKIPPED_FULL_JOB,
            head=CURRENT,
            run_id=DOCS_RUN,
            steps=[],
            conclusion="skipped",
        ),
    ]
    return jobs


def _context(tmp_path: Path, monkeypatch, *, changed_paths=None, run_mutation=None):
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "before": BASE,
                "after": CURRENT,
                "ref": "refs/heads/develop",
                "forced": False,
                "deleted": False,
            }
        ),
        encoding="utf-8",
    )
    for name, value in {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_REF_NAME": "develop",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKFLOW": "Checkpoint Source Gates",
        "GITHUB_WORKFLOW_REF": (
            f"{REPOSITORY}/.github/workflows/"
            "checkpoint-source-gates.yml@refs/heads/develop"
        ),
        "GITHUB_SHA": CURRENT,
        "GITHUB_RUN_ID": str(CURRENT_RUN),
        "GITHUB_REPOSITORY_ID": "7",
        "GITHUB_EVENT_PATH": str(event_path),
    }.items():
        monkeypatch.setenv(name, value)
    if run_mutation is None:
        states = iter(
            [
                {
                    "head": CURRENT,
                    "tree": CURRENT_TREE,
                    "branch": "develop",
                    "porcelain": "",
                },
                {
                    "head": CURRENT,
                    "tree": CURRENT_TREE,
                    "branch": "develop",
                    "porcelain": "",
                },
            ]
        )
    else:
        states = iter(
            [
                {
                    "head": CURRENT,
                    "tree": CURRENT_TREE,
                    "branch": "develop",
                    "porcelain": "",
                },
                {
                    "head": "f" * 40,
                    "tree": CURRENT_TREE,
                    "branch": "develop",
                    "porcelain": "",
                },
            ]
        )
    monkeypatch.setattr(runner, "_git_state", lambda _root: next(states))

    def git(_root, *args):
        if args[:3] == ("remote", "get-url", "origin"):
            return f"https://github.com/{REPOSITORY}.git"
        if args[:2] == ("merge-base", "--is-ancestor"):
            return ""
        if args[:3] == ("rev-list", "--ancestry-path", "--reverse"):
            return f"{CERTIFIED}\n{CURRENT}"
        if args[:3] == ("rev-list", "--parents", "-n"):
            commit = args[4]
            return f"{commit} {BASE if commit == CERTIFIED else CERTIFIED}"
        if args[:2] == ("diff", "--name-only"):
            return (
                "docs/PROJECT_STATUS.md"
                if changed_paths is None
                else "\n".join(changed_paths)
            )
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git_output", git)
    workflow = {
        "id": WORKFLOW_ID,
        "name": "Checkpoint Source Gates",
        "path": ".github/workflows/checkpoint-source-gates.yml",
        "state": "active",
    }
    feature_run = _run(FEATURE_RUN, CERTIFIED, FEATURE, conclusion="success")
    docs_run = _run(DOCS_RUN, CURRENT, FEATURE, conclusion="success")
    if run_mutation == "attempt2":
        feature_run["run_attempt"] = 2
    if run_mutation == "failed":
        feature_run["conclusion"] = "failure"
    if run_mutation == "docs_failed":
        docs_run["conclusion"] = "failure"
    responses = {
        f"repos/{REPOSITORY}": {"full_name": REPOSITORY, "id": 7},
        f"repos/{REPOSITORY}/actions/workflows/checkpoint-source-gates.yml": workflow,
        f"repos/{REPOSITORY}/git/commits/{CERTIFIED}": {
            "sha": CERTIFIED,
            "tree": {"sha": CERTIFIED_TREE},
        },
        (
            f"repos/{REPOSITORY}/actions/workflows/{WORKFLOW_ID}/runs?"
            f"head_sha={CERTIFIED}&event=push&per_page=100"
        ): {
            "total_count": 1,
            "workflow_runs": [feature_run],
        },
        f"repos/{REPOSITORY}/actions/runs/{FEATURE_RUN}": feature_run,
        (
            f"repos/{REPOSITORY}/actions/runs/{FEATURE_RUN}/attempts/1/"
            "jobs?per_page=100"
        ): {
            "total_count": len(_feature_jobs()),
            "jobs": _feature_jobs(),
        },
        (
            f"repos/{REPOSITORY}/actions/workflows/{WORKFLOW_ID}/runs?"
            f"head_sha={CURRENT}&event=push&per_page=100"
        ): {
            "total_count": 1,
            "workflow_runs": [docs_run],
        },
        f"repos/{REPOSITORY}/actions/runs/{DOCS_RUN}": docs_run,
        f"repos/{REPOSITORY}/actions/runs/{DOCS_RUN}/attempts/1/jobs?per_page=100": {
            "total_count": len(_docs_jobs()),
            "jobs": _docs_jobs(),
        },
    }
    monkeypatch.setattr(runner, "_github_ci_metadata", responses.__getitem__)
    return tmp_path


def _resolve(tmp_path, monkeypatch, **kwargs):
    return successor.resolve_develop_ci_reuse(
        tmp_path,
        "FULL",
        exact_resolver=lambda _root, _mode: {
            "reuse": False,
            "reason": "no_unique_certification",
        },
    )


def test_exact_head_reuse_is_returned_unchanged(tmp_path, monkeypatch):
    result = successor.resolve_develop_ci_reuse(
        tmp_path,
        "FULL",
        exact_resolver=lambda _root, _mode: {
            "reuse": True,
            "reason": "exact_feature_certification",
            "run_id": 12,
        },
    )
    assert result == {
        "reuse": True,
        "reason": "exact_feature_certification",
        "run_id": 12,
    }


def test_incident_reuses_certified_source_with_docs_only_descendant(
    tmp_path, monkeypatch
):
    _context(tmp_path, monkeypatch)
    result = _resolve(tmp_path, monkeypatch)
    assert result["reuse"] is True, result
    assert result["reason"] == successor.REASON
    assert result["reuse_kind"] == successor.REASON
    assert result["certified_source_head"] == CERTIFIED
    assert result["current_develop_head"] == CURRENT
    assert result["certified_feature_run_id"] == FEATURE_RUN
    assert result["current_docs_gate_run_id"] == DOCS_RUN
    assert result["docs_only_descendants"][0]["paths"] == ["docs/PROJECT_STATUS.md"]


@pytest.mark.parametrize(
    "paths",
    [
        ["src/example.py"],
        ["tests/example.py"],
        ["scripts/example.py"],
        [".github/workflows/checkpoint-source-gates.yml"],
        ["pyproject.toml"],
        ["registry.json"],
        ["unknown/path.bin"],
    ],
)
def test_non_docs_suffix_blocks_reuse(tmp_path, monkeypatch, paths):
    _context(tmp_path, monkeypatch, changed_paths=paths)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


@pytest.mark.parametrize("mutation", ["attempt2", "failed", "docs_failed"])
def test_failed_or_non_original_gate_blocks_reuse(tmp_path, monkeypatch, mutation):
    _context(tmp_path, monkeypatch, run_mutation=mutation)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_source_mutation_during_proof_fails_closed(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch, run_mutation="source_changed")
    result = _resolve(tmp_path, monkeypatch)
    assert result == {"reuse": False, "reason": "integration_source_changed"}


@pytest.mark.parametrize("field", ["forced", "deleted"])
def test_forced_or_deleted_push_blocks_reuse(tmp_path, monkeypatch, field):
    _context(tmp_path, monkeypatch)
    event_path = tmp_path / "event.json"
    event = json.loads(event_path.read_text(encoding="utf-8"))
    event[field] = True
    event_path.write_text(json.dumps(event), encoding="utf-8")
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_non_fast_forward_push_blocks_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._git_output

    def non_fast_forward(root, *args):
        if args[:2] == ("merge-base", "--is-ancestor"):
            raise RuntimeError("not an ancestor")
        return original(root, *args)

    monkeypatch.setattr(runner, "_git_output", non_fast_forward)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_candidate_outside_current_push_range_blocks_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._git_output

    def outside_range(root, *args):
        if args[:3] == ("rev-list", "--ancestry-path", "--reverse"):
            return CURRENT
        return original(root, *args)

    monkeypatch.setattr(runner, "_git_output", outside_range)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_nonancestor_certified_candidate_blocks_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._git_output

    def nonancestor(root, *args):
        if args[:2] == ("merge-base", "--is-ancestor") and args[2:] == (
            CERTIFIED,
            CURRENT,
        ):
            raise RuntimeError("certified source is not an ancestor")
        return original(root, *args)

    monkeypatch.setattr(runner, "_git_output", nonancestor)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_incomplete_metadata_blocks_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._github_ci_metadata

    def incomplete(endpoint):
        value = original(endpoint)
        if endpoint.endswith(f"runs?head_sha={CERTIFIED}&event=push&per_page=100"):
            return {**value, "total_count": 2}
        return value

    monkeypatch.setattr(runner, "_github_ci_metadata", incomplete)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_ambiguous_multiple_feature_certifications_block_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._github_ci_metadata

    def ambiguous(endpoint):
        value = original(endpoint)
        if endpoint.endswith(f"runs?head_sha={CERTIFIED}&event=push&per_page=100"):
            return {"total_count": 2, "workflow_runs": value["workflow_runs"] * 2}
        return value

    monkeypatch.setattr(runner, "_github_ci_metadata", ambiguous)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_multiple_qualifying_certified_ancestors_block_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original_metadata = runner._github_ci_metadata
    original = runner._git_output
    second_run = _run(SECOND_FEATURE_RUN, SECOND_CERTIFIED, FEATURE)
    second_jobs = deepcopy(_feature_jobs())
    for job in second_jobs:
        job["run_id"] = SECOND_FEATURE_RUN
        job["head_sha"] = SECOND_CERTIFIED

    def metadata(endpoint):
        if endpoint == f"repos/{REPOSITORY}/git/commits/{SECOND_CERTIFIED}":
            return {"sha": SECOND_CERTIFIED, "tree": {"sha": SECOND_TREE}}
        if endpoint.endswith(
            f"runs?head_sha={SECOND_CERTIFIED}&event=push&per_page=100"
        ):
            return {"total_count": 1, "workflow_runs": [second_run]}
        if endpoint == f"repos/{REPOSITORY}/actions/runs/{SECOND_FEATURE_RUN}":
            return second_run
        if endpoint == (
            f"repos/{REPOSITORY}/actions/runs/{SECOND_FEATURE_RUN}/attempts/1/"
            "jobs?per_page=100"
        ):
            return {"total_count": len(second_jobs), "jobs": second_jobs}
        return original_metadata(endpoint)

    monkeypatch.setattr(runner, "_github_ci_metadata", metadata)

    def multiple_candidates(root, *args):
        if args[:3] == ("rev-list", "--ancestry-path", "--reverse"):
            return f"{CERTIFIED}\n{SECOND_CERTIFIED}\n{CURRENT}"
        if args[:3] == ("rev-list", "--parents", "-n"):
            commit = args[4]
            parent = {
                CERTIFIED: BASE,
                SECOND_CERTIFIED: CERTIFIED,
                CURRENT: SECOND_CERTIFIED,
            }[commit]
            return f"{commit} {parent}"
        if args[:2] == ("diff", "--name-only"):
            return "docs/PROJECT_STATUS.md"
        return original(root, *args)

    monkeypatch.setattr(runner, "_git_output", multiple_candidates)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_missing_docs_descendant_gate_blocks_reuse(tmp_path, monkeypatch):
    _context(tmp_path, monkeypatch)
    original = runner._github_ci_metadata

    def missing_gate(endpoint):
        if endpoint.endswith(f"runs?head_sha={CURRENT}&event=push&per_page=100"):
            return {"total_count": 0, "workflow_runs": []}
        return original(endpoint)

    monkeypatch.setattr(runner, "_github_ci_metadata", missing_gate)
    assert _resolve(tmp_path, monkeypatch)["reuse"] is False


def test_multiple_docs_only_descendants_are_proven_as_a_bounded_suffix(
    tmp_path, monkeypatch
):
    _context(tmp_path, monkeypatch)
    original_metadata = runner._github_ci_metadata
    original = runner._git_output
    middle = "1" * 40

    def metadata(endpoint):
        if endpoint == f"repos/{REPOSITORY}/git/commits/{middle}":
            return {"sha": middle, "tree": {"sha": "2" * 40}}
        if endpoint.endswith(f"runs?head_sha={middle}&event=push&per_page=100"):
            return {"total_count": 0, "workflow_runs": []}
        return original_metadata(endpoint)

    monkeypatch.setattr(runner, "_github_ci_metadata", metadata)

    def multiple_suffix(root, *args):
        if args[:3] == ("rev-list", "--ancestry-path", "--reverse"):
            return (
                f"{CERTIFIED}\n{CURRENT}"
                if args[3] == f"{BASE}..{CURRENT}"
                else f"{middle}\n{CURRENT}"
            )
        if args[:3] == ("rev-list", "--parents", "-n"):
            commit = args[4]
            parent = BASE if commit == CERTIFIED else CERTIFIED
            if commit == CURRENT:
                parent = middle
            return f"{commit} {parent}"
        if args[:2] == ("diff", "--name-only"):
            return "docs/PROJECT_STATUS.md"
        return original(root, *args)

    monkeypatch.setattr(runner, "_git_output", multiple_suffix)
    result = _resolve(tmp_path, monkeypatch)
    assert result["reuse"] is True
    assert [item["commit"] for item in result["docs_only_descendants"]] == [
        middle,
        CURRENT,
    ]


def test_workflow_projection_skips_canonical_and_fallback_routes():
    workflow = (
        Path(runner.__file__).resolve().parents[1]
        / ".github/workflows/checkpoint-source-gates.yml"
    )
    text = workflow.read_text(encoding="utf-8")
    assert "needs.source-static.outputs.reuse_certification != 'true'" in text
    assert (
        "needs.source-static.outputs.mode != 'DOCS_ONLY' && "
        "needs.source-static.outputs.certification_profile == 'full'"
    ) in text
    assert "needs.source-static.outputs.certification_profile == 'robinhood'" in text
    assert "needs.source-static.outputs.certification_profile == 'full'" in text
